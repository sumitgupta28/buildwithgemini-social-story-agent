"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import uuid
import time
import re


import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    FilePart,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TextPart,
    TransportProtocol,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

if "AGENT_ENGINE_RESOURCE_NAME" in os.environ:
    RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
else:
    import json
    meta_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            RESOURCE = json.load(f)["remote_agent_runtime_id"]
    else:
        RESOURCE = "projects/973976208178/locations/us-east1/reasoningEngines/7431689252091461632"

# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Clear cached context IDs on error so subsequent requests start a fresh session
    _contexts.clear()
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        # Agent Runtime does not serve a public card URL, so point the client at
        # the passthrough base for message sends.
        card.url = A2A_BASE
        _card = card
    return _card


def _clean_text_part(text: str) -> str:
    """Rewrite any internal generativelanguage.googleapis.com URIs to local /static/cartoons/ paths."""
    if not text:
        return text
    pattern = r'https?://generativelanguage\.googleapis\.com/[^\s\)\"\']+/([a-zA-Z0-9_\-\.]+\.(?:jpg|jpeg|png))'
    cleaned = re.sub(pattern, r'/static/cartoons/\1', text)
    return cleaned


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI."""
    out: list[dict] = []
    if not parts:
        return out
    for p in parts:
        root = getattr(p, "root", p)
        if isinstance(root, TextPart) and getattr(root, "text", None):
            out.append({"kind": "text", "text": _clean_text_part(root.text)})
        elif getattr(root, "data", None) is not None:
            meta = getattr(root, "metadata", None) or {}
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": root.data})
            else:
                out.append({"kind": "text", "text": _clean_text_part(str(root.data))})
        elif isinstance(root, FilePart):
            uri = getattr(getattr(root, "file", None), "uri", None)
            if uri:
                out.append({"kind": "text", "text": _clean_text_part(uri)})
        elif hasattr(root, "text") and getattr(root, "text", None):
            out.append({"kind": "text", "text": _clean_text_part(str(root.text))})
    return out



@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    if body.get("reset_session") or body.get("new_session"):
        _contexts.pop(user_id, None)
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=180.0) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            context_id=_contexts.get(user_id),
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            if not isinstance(event, tuple):
                continue
            task, update = event
            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
            
            if update is not None:
                if isinstance(update, TaskArtifactUpdateEvent):
                    got_artifact_update = True
                    parts.extend(_extract_parts(getattr(getattr(update, "artifact", None), "parts", [])))
                elif hasattr(update, "parts"):
                    p_extracted = _extract_parts(getattr(update, "parts", []))
                    if p_extracted:
                        got_artifact_update = True
                        parts.extend(p_extracted)

        # Non-streaming fallback: pull parts from final task's artifacts, history, or output.
        if not parts and last_task is not None:
            if hasattr(last_task, "artifacts") and last_task.artifacts:
                for artifact in last_task.artifacts:
                    parts.extend(_extract_parts(getattr(artifact, "parts", [])))
            if not parts and hasattr(last_task, "history") and last_task.history:
                for msg_item in reversed(last_task.history):
                    role_val = getattr(msg_item, "role", None)
                    role_str = str(getattr(role_val, "value", role_val))
                    if role_val == Role.agent or role_str in ["agent", "assistant", "model"]:
                        p_extracted = _extract_parts(getattr(msg_item, "parts", []))
                        if p_extracted:
                            parts.extend(p_extracted)
                            break
            if not parts and hasattr(last_task, "status_message") and last_task.status_message:
                parts.append({"kind": "text", "text": str(last_task.status_message)})

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


_PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
<rect width="800" height="600" fill="#1e293b"/>
<text x="400" y="280" font-family="sans-serif" font-size="28" fill="#f8fafc" text-anchor="middle" font-weight="bold">Social Story Illustration</text>
<text x="400" y="330" font-family="sans-serif" font-size="18" fill="#94a3b8" text-anchor="middle">Image is being generated or archived</text>
</svg>"""

@app.middleware("http")
async def cartoon_proxy_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static/cartoons/") and request.method in ("GET", "HEAD"):
        filename = path.replace("/static/cartoons/", "")
        local_path = os.path.join(os.path.dirname(__file__), "static", "cartoons", filename)
        if os.path.exists(local_path):
            from fastapi.responses import FileResponse
            return FileResponse(local_path)
        
        # GCS proxy fallback
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            try:
                import google.auth
                _, project_id = google.auth.default()
            except Exception:
                pass
        if not project_id:
            project_id = "qwiklabs-gcp-01-eb84874d9448"

        bucket_name = os.environ.get("MEDIA_BUCKET_NAME", f"social-story-media-{project_id}")
        gcs_url = f"https://storage.googleapis.com/{bucket_name}/story_cartoons/{filename}"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(gcs_url)
                if resp.status_code == 200:
                    media_type = resp.headers.get("content-type", "image/jpeg")
                    if request.method == "HEAD":
                        from fastapi.responses import Response
                        return Response(content=b"", media_type=media_type, headers={"content-length": str(len(resp.content))})
                    from fastapi.responses import Response
                    return Response(content=resp.content, media_type=media_type)
        except Exception as e:
            print(f"GCS Proxy Fetch Error: {e}")

        # SVG placeholder fallback for missing images to prevent broken UI icons or 404 console errors
        from fastapi.responses import Response
        if request.method == "HEAD":
            return Response(content=b"", media_type="image/svg+xml", headers={"content-length": str(len(_PLACEHOLDER_SVG.encode()))})
        return Response(content=_PLACEHOLDER_SVG.encode("utf-8"), media_type="image/svg+xml")

    return await call_next(request)

@app.get("/static/cartoons/{filename}")
async def get_cartoon_file(filename: str):
    local_path = os.path.join(os.path.dirname(__file__), "static", "cartoons", filename)
    if os.path.exists(local_path):
        from fastapi.responses import FileResponse
        return FileResponse(local_path)
    
    # GCS proxy fallback
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        try:
            import google.auth
            _, project_id = google.auth.default()
        except Exception:
            pass
    if not project_id:
        project_id = "qwiklabs-gcp-01-eb84874d9448"

    bucket_name = os.environ.get("MEDIA_BUCKET_NAME", f"social-story-media-{project_id}")
    gcs_url = f"https://storage.googleapis.com/{bucket_name}/story_cartoons/{filename}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(gcs_url)
            if resp.status_code == 200:
                from fastapi.responses import Response
                return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
    except Exception as e:
        print(f"GCS Proxy Fetch Error: {e}")
            
    from fastapi.responses import Response
    return Response(content=_PLACEHOLDER_SVG.encode("utf-8"), media_type="image/svg+xml")



DEFAULT_SCENARIOS = [
    {
        "id": "dentist",
        "category": "medical",
        "title": "Dentist Visit",
        "icon": "🦷",
        "description": "Visiting the dentist for a tooth checkup with Mom Yamini.",
        "prompt": "Create a visual social story for Aarav visiting the dentist with Mom Yamini"
    },
    {
        "id": "haircut",
        "category": "routines",
        "title": "Haircut Time",
        "icon": "✂️",
        "description": "Getting a gentle haircut with soft electric clippers.",
        "prompt": "Create a visual social story for Aarav getting a gentle haircut"
    },
    {
        "id": "school_bus",
        "category": "school",
        "title": "Riding the School Bus",
        "icon": "🚌",
        "description": "Boarding the yellow school bus and wearing noise-canceling headphones.",
        "prompt": "Create a visual social story for Aarav riding the school bus"
    },
    {
        "id": "doctor",
        "category": "medical",
        "title": "Doctor Checkup",
        "icon": "🏥",
        "description": "A calm pediatric checkup listening to heartbeat with stethoscope.",
        "prompt": "Create a visual social story for Aarav at the doctor checkup"
    },
    {
        "id": "airport",
        "category": "transitions",
        "title": "Airport Security",
        "icon": "✈️",
        "description": "Passing through airport security luggage scanner with blue teddy bear.",
        "prompt": "Create a visual social story for Aarav passing airport security"
    },
    {
        "id": "dog_meeting",
        "category": "social",
        "title": "Meeting a Friendly Dog",
        "icon": "🐕",
        "description": "Asking owner before gently petting a friendly golden retriever.",
        "prompt": "Create a visual social story for Aarav meeting a friendly dog"
    }
]

CUSTOM_SCENARIOS = []

@app.get("/api/scenarios")
async def get_scenarios():
    firestore_scenarios = []
    try:
        from app.family_tools import get_firestore_client
        db = get_firestore_client()
        if db:
            docs = db.collection("custom_scenarios").stream()
            for doc in docs:
                firestore_scenarios.append(doc.to_dict())
    except Exception as e:
        # Gracefully handle uninitialized Firestore DB or pending IAM permissions
        pass


    all_scenarios = list(DEFAULT_SCENARIOS)
    existing_ids = {s["id"] for s in all_scenarios}

    for s in CUSTOM_SCENARIOS + firestore_scenarios:
        if isinstance(s, dict) and s.get("id") and s["id"] not in existing_ids:
            all_scenarios.append(s)
            existing_ids.add(s["id"])

    return all_scenarios

@app.post("/api/scenarios")
async def add_scenario(request: Request):
    try:
        body = await request.json()
        title = body.get("title", "").strip()
        category = body.get("category", "routines").strip()
        description = body.get("description", "").strip()
        prompt = body.get("prompt", "").strip()
        icon = body.get("icon", "✨").strip()

        if not title or not prompt:
            return JSONResponse(status_code=400, content={"error": "Title and prompt are required."})

        scenario_id = f"custom_{int(time.time() * 1000)}"
        scenario_data = {
            "id": scenario_id,
            "category": category,
            "title": title,
            "icon": icon,
            "description": description,
            "prompt": prompt
        }

        CUSTOM_SCENARIOS.append(scenario_data)

        try:
            from app.family_tools import get_firestore_client
            db = get_firestore_client()
            if db:
                db.collection("custom_scenarios").document(scenario_id).set(scenario_data)
        except Exception as e:
            print(f"Error saving custom scenario to Firestore: {e}")

        return scenario_data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/generate_video")
async def generate_video_api(request: Request):
    try:
        body = await request.json()
        title = body.get("title", "Aarav's Social Story").strip()
        prompt = body.get("prompt", "").strip()
        
        from app.video_tools import generate_story_video
        panel_prompts = [
            f"{title} - Step 1: Getting ready calmly with Mom Yamini",
            f"{title} - Step 2: Arriving at destination with blue teddy bear",
            f"{title} - Step 3: Step-by-step transition wearing noise-canceling headphones",
            f"{title} - Step 4: Finishing successfully with a big smile and receiving a star sticker reward"
        ]
        video_url = await generate_story_video(panel_prompts=panel_prompts, story_title=title)
        return {"video_url": video_url}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/config")
async def get_config():
    return {
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "")
    }

_static_dir = os.path.join(os.path.dirname(__file__), "static")

app.mount("/", StaticFiles(directory=_static_dir if os.path.exists(_static_dir) else "static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
