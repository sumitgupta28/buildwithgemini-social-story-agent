import os
import uuid
from google import genai
from google.genai import types
from google.cloud import storage
from google.adk.tools import ToolContext

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-01-b5f16f2f275a")
BUCKET_NAME = os.environ.get(
    "MEDIA_BUCKET_NAME", f"social-story-media-{PROJECT_ID}"
)

async def generate_cartoon_illustration(
    prompt: str,
    tool_context: ToolContext = None,
) -> str:
    """Generates a friendly 2D cartoon storybook illustration using Gemini Image Gen.

    Args:
        prompt: Description of the cartoon scene (e.g. '6-year-old boy Aarav sitting in a dentist chair with Mom Yamini').
        tool_context: ADK ToolContext used to save artifact files to Playground.

    Returns:
        Public HTTPS URL of the generated image saved in Cloud Storage.
    """
    try:
        styled_prompt = (
            f"A warm, friendly, 2D digital cartoon storybook illustration for children. "
            f"Non-scary, clean lines, vibrant cheerful colors. Scene: {prompt}"
        )

        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
        )

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=styled_prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        for candidate in getattr(response, "candidates", []):
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_bytes = part.inline_data.data
                        if part.inline_data.mime_type:
                            mime_type = part.inline_data.mime_type
                        break
                if image_bytes:
                    break

        if not image_bytes:
            return "Failed to generate cartoon illustration."

        filename = f"cartoon_{uuid.uuid4().hex[:8]}.jpg"

        if tool_context and hasattr(tool_context, "save_artifact"):
            try:
                artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
                if hasattr(res, "__await__"):
                    await res
            except Exception:
                pass

        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"story_cartoons/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
        return public_url

    except Exception as e:
        return f"Error generating cartoon illustration: {str(e)}"

import asyncio

async def generate_comic_book_page(
    panel_prompts: list[str],
    tool_context: ToolContext = None,
) -> list[dict]:
    """Generates a 4 to 5 block comic book page layout with cartoon panel illustrations.

    Args:
        panel_prompts: List of 4 to 5 scene descriptions for each comic panel step (e.g. ['Aarav putting on shoes with Mom Yamini', 'Aarav walking into dentist office', 'Aarav sitting in dentist chair', 'Aarav getting a star sticker']).
        tool_context: ADK ToolContext used to save artifact files to Playground.

    Returns:
        List of dictionaries containing panel number, scene description prompt, and cartoon image public HTTPS URL.
    """
    if not panel_prompts:
        return []

    # Limit to 5 panels max for optimal performance and visual density
    prompts = panel_prompts[:5]

    async def _gen_panel(idx: int, p_text: str):
        url = await generate_cartoon_illustration(p_text, tool_context=tool_context)
        return {
            "panel": idx + 1,
            "description": p_text,
            "image_url": url,
        }

    tasks = [_gen_panel(i, p) for i, p in enumerate(prompts)]
    panels = await asyncio.gather(*tasks)
    return list(panels)

