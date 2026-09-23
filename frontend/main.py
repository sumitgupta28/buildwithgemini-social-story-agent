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
from app.app_utils.project_id import get_project_id
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
        try:
            project_id = get_project_id()
        except Exception:
            project_id = "unknown"

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
    try:
        project_id = get_project_id()
    except Exception:
        project_id = "unknown"

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
        "id": "school_bus",
        "category": "school",
        "title": "Riding the School Bus",
        "icon": "🚌",
        "description": "Boarding the yellow school bus calmly with noise-canceling headphones.",
        "prompt": "Riding the School Bus"
    },
    {
        "id": "dentist",
        "category": "medical",
        "title": "Dentist Visit",
        "icon": "🦷",
        "description": "Visiting the dentist for a friendly teeth checkup with Mom.",
        "prompt": "Dentist Visit"
    },
    {
        "id": "haircut",
        "category": "routines",
        "title": "Haircut Time",
        "icon": "✂️",
        "description": "Getting a gentle haircut with quiet electric clippers.",
        "prompt": "Haircut Time"
    },
    {
        "id": "doctor",
        "category": "medical",
        "title": "Doctor Checkup",
        "icon": "🏥",
        "description": "A calm pediatric checkup listening to heartbeat with stethoscope.",
        "prompt": "Doctor Checkup"
    },
    {
        "id": "airport",
        "category": "transitions",
        "title": "Airport Security",
        "icon": "✈️",
        "description": "Passing through airport security luggage scanner with blue teddy bear.",
        "prompt": "Airport Security"
    },
    {
        "id": "dog_meeting",
        "category": "social",
        "title": "Meeting a Friendly Dog",
        "icon": "🐕",
        "description": "Asking owner before gently petting a friendly golden retriever.",
        "prompt": "Meeting a Friendly Dog"
    }
]

CUSTOM_SCENARIOS = []

@app.get("/api/profile")
async def get_profile_api():
    from app.family_tools import get_active_profile
    return get_active_profile()

@app.post("/api/profile")
async def update_profile_api(request: Request):
    try:
        body = await request.json()
        from app.family_tools import update_active_profile
        updated = update_active_profile(body)
        return updated
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

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

        # Check for new characters mentioned in title/description and auto-add to profile
        from app.family_tools import ensure_character_in_profile
        lower_txt = (title + " " + description + " " + prompt).lower()
        if "dentist" in lower_txt:
            ensure_character_in_profile("Dentist", "Dr. Smith")
        elif "barber" in lower_txt or "haircut" in lower_txt:
            ensure_character_in_profile("Barber", "Mr. Marco")
        elif "doctor" in lower_txt:
            ensure_character_in_profile("Doctor", "Dr. Sam")
        elif "teacher" in lower_txt or "school" in lower_txt:
            ensure_character_in_profile("Teacher", "Ms. Priya")

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

def _build_dialogue_panels(title: str, topic: str) -> list[str]:
    from app.family_tools import get_active_profile, ensure_character_in_profile
    profile = get_active_profile()
    c_name = profile.get("child_name", "Child")
    m_name = profile.get("mother_name", "Mom")

    t_lower = (title + " " + topic).lower()
    
    if "bus" in t_lower:
        teacher_name = ensure_character_in_profile("Teacher", "Ms. Priya")
        return [
            f"Waiting for Bus | {m_name}: We are waiting for the yellow bus! | {c_name}: My blue backpack is ready!",
            f"Boarding Bus | Bus Driver: Good morning {c_name}! | {c_name}: Good morning! I hold handrail.",
            f"Riding Bus | Friend: Sit with me {c_name}! | {c_name}: Headphones keep ride quiet.",
            f"Arriving at School | {teacher_name}: Welcome to school {c_name}! | {c_name}: I did a great job!"
        ]
    elif "dentist" in t_lower:
        dentist_name = ensure_character_in_profile("Dentist", "Dr. Smith")
        return [
            f"Preparing for Dentist | {m_name}: {dentist_name} will check teeth! | {c_name}: Will teeth be shiny?",
            f"Arriving at Clinic | {m_name}: Look at the smile sign! | {c_name}: I see the fish tank!",
            f"Dental Chair | {dentist_name}: Let's count shiny teeth! | {c_name}: 1... 2... 3... sitting still!",
            f"Finishing Checkup | {dentist_name}: You were super brave! | {c_name}: I got a star sticker!"
        ]
    elif "haircut" in t_lower:
        barber_name = ensure_character_in_profile("Barber", "Mr. Marco")
        return [
            f"Entering Barber | {m_name}: Time for a quick haircut! | {c_name}: The cape is smooth.",
            f"Styling Chair | {barber_name}: Ready for scissor clicks? | {c_name}: Yes! Holding teddy.",
            f"Trimming Hair | {barber_name}: Trimming top hair! | {c_name}: Clippers tickle softly.",
            f"Handsome Haircut | {m_name}: Look in the mirror! | {c_name}: I look handsome!"
        ]
    elif "doctor" in t_lower:
        doctor_name = ensure_character_in_profile("Doctor", "Dr. Sam")
        return [
            f"Doctor Waiting Room | {m_name}: {doctor_name} listens to heartbeat. | {c_name}: Playing with wooden beads.",
            f"Stethoscope Test | {doctor_name}: Stethoscope is cool! | {c_name}: Thump-thump heartbeat!",
            f"Measuring Height | Nurse: Stand tall like a tree! | {c_name}: I am getting taller!",
            f"All Done | {doctor_name}: High five buddy! | {c_name}: High five!"
        ]
    elif "airport" in t_lower:
        return [
            f"Packing Bags | {m_name}: Bags go on scanner! | {c_name}: Teddy gets scanned!",
            f"Security Arch | Officer: Walk through slowly! | {c_name}: Walking calmly.",
            f"Picking Up Teddy | {m_name}: Here is teddy back! | {c_name}: Teddy is safe!",
            f"Boarding Plane | {m_name}: Ready to fly! | {c_name}: Big airplanes outside!"
        ]
    elif "dog" in t_lower:
        return [
            f"Seeing Dog | {c_name}: May I pet your dog? | Owner: Max loves gentle pets!",
            f"Gentle Sniff | {m_name}: Let Max sniff your hand! | {c_name}: His nose is soft.",
            f"Petting Fur | {c_name}: Max wags his tail! | Owner: He likes you {c_name}!",
            f"Saying Goodbye | {c_name}: Bye Max! | {m_name}: Great job asking!"
        ]
    else:
        clean_topic = topic if topic else title
        teacher_name = ensure_character_in_profile("Teacher", "Ms. Priya")
        return [
            f"Step 1: Preparing | {m_name}: We are starting {clean_topic}! | {c_name}: I am ready!",
            f"Step 2: Transitioning | {m_name}: Taking it step by step! | {c_name}: Holding blue teddy.",
            f"Step 3: Following Steps | {teacher_name}: You are doing great {c_name}! | {c_name}: I am following along!",
            f"Step 4: Success | {m_name}: Proud of you {c_name}! | {c_name}: I did it!"
        ]

@app.post("/api/generate_video")
async def generate_video_api(request: Request):
    try:
        body = await request.json()
        from app.family_tools import get_active_profile
        profile = get_active_profile()
        c_name = profile.get("child_name", "Child")
        title = body.get("title", f"{c_name}'s Social Story").strip()
        prompt = body.get("prompt", "").strip()
        
        from app.video_tools import generate_story_video
        panel_prompts = _build_dialogue_panels(title, prompt)
        video_url = await generate_story_video(panel_prompts=panel_prompts, story_title=title)
        return {"video_url": video_url}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/generate_comic")
async def generate_comic_api(request: Request):
    try:
        body = await request.json()
        from app.family_tools import get_active_profile
        profile = get_active_profile()
        c_name = profile.get("child_name", "Child")
        m_name = profile.get("mother_name", "Mom")
        title = body.get("title", f"{c_name}'s Social Story").strip()
        prompt = body.get("prompt", "").strip()
        
        from app.image_tools import generate_comic_book_page
        panel_prompts = _build_dialogue_panels(title, prompt)
        image_url = await generate_comic_book_page(
            panel_prompts=panel_prompts,
            story_title=title,
            child_name=c_name,
            mother_name=m_name
        )
        return {"image_url": image_url}
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
