import os
import uuid
from google import genai
from google.genai import types
from google.cloud import storage
from google.adk.tools import ToolContext

def _get_project_id() -> str:
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return os.environ["GOOGLE_CLOUD_PROJECT"]
    try:
        import google.auth
        _, project = google.auth.default()
        if project:
            return project
    except Exception:
        pass
    return "qwiklabs-gcp-02-1f7e291be017"

PROJECT_ID = "qwiklabs-gcp-02-1f7e291be017"
BUCKET_NAME = "social-story-media-qwiklabs-gcp-02-1f7e291be017"

import io
import math
from PIL import Image, ImageDraw, ImageFont

def _wrap_text(text: str, max_chars: int = 50) -> list[str]:
    words = text.split()
    lines = []
    curr = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) + 1 > max_chars:
            lines.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + 1
    if curr:
        lines.append(" ".join(curr))
    return lines[:2]

def _composite_panels_to_single_image(panel_images_bytes: list[bytes], panel_subtitles: list[str] = None) -> bytes:
    images = []
    for b in panel_images_bytes:
        if b:
            try:
                img = Image.open(io.BytesIO(b)).convert("RGB")
                images.append(img)
            except Exception as err:
                print(f"Failed to parse panel image bytes: {err}")
    if not images:
        return None

    num_panels = len(images)
    cols = 2
    rows = math.ceil(num_panels / cols)

    panel_w = 500
    img_h = 350
    caption_h = 65
    panel_h = img_h + caption_h
    margin = 20
    header_h = 70
    footer_h = 10

    canvas_w = (cols * panel_w) + ((cols + 1) * margin)
    canvas_h = header_h + (rows * panel_h) + ((rows + 1) * margin) + footer_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), "#f4f7fe")
    draw = ImageDraw.Draw(canvas)

    # Header Banner
    draw.rectangle([margin, margin, canvas_w - margin, header_h], fill="#4361ee")
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    draw.text((canvas_w // 2, margin + 35), "BUDDYCRAFT VISUAL SOCIAL STORY", fill="#ffffff", font=title_font, anchor="mm")

    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        x = margin + c * (panel_w + margin)
        y = header_h + margin + r * (panel_h + margin)

        # Image section
        resized_img = img.resize((panel_w, img_h), Image.Resampling.LANCZOS)
        canvas.paste(resized_img, (x, y))

        # Subtitle caption section (No Panel 1 / Panel 2 badges!)
        cap_y = y + img_h
        draw.rectangle([x, cap_y, x + panel_w, y + panel_h], fill="#ffffff")
        draw.rectangle([x, y, x + panel_w, y + panel_h], outline="#3a0ca3", width=4)

        if panel_subtitles and i < len(panel_subtitles):
            raw_sub = panel_subtitles[i]
            # Strip markdown formatting if any
            clean_sub = raw_sub.replace("*", "").replace("#", "").strip()
            lines = _wrap_text(clean_sub, max_chars=48)
            if len(lines) == 1:
                draw.text((x + panel_w // 2, cap_y + caption_h // 2), lines[0], fill="#1e293b", font=sub_font, anchor="mm")
            elif len(lines) >= 2:
                draw.text((x + panel_w // 2, cap_y + 20), lines[0], fill="#1e293b", font=sub_font, anchor="mm")
                draw.text((x + panel_w // 2, cap_y + 42), lines[1], fill="#1e293b", font=sub_font, anchor="mm")

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue()

async def _fetch_raw_panel_bytes(prompt: str) -> bytes:
    try:
        styled_prompt = (
            f"A warm, friendly, 2D digital cartoon storybook illustration for children. "
            f"Non-scary, clean lines, vibrant cheerful colors. "
            f"CLOTHING NAME PRINTS: Do NOT draw floating text tags, speech bubbles, or wall signs for character names. "
            f"Instead, print the young child's name clearly across the front of his t-shirt/shirt (e.g. 'AARAV' printed on his shirt) "
            f"and print the mom's name clearly on her top/badge (e.g. 'YAMINI' printed on her shirt/pendant). "
            f"Scene: {prompt}"
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
        for candidate in getattr(response, "candidates", []):
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_bytes = part.inline_data.data
                        break
                if image_bytes:
                    break
        return image_bytes
    except Exception as e:
        print(f"Error generating raw panel bytes: {e}")
        return None

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
        image_bytes = await _fetch_raw_panel_bytes(prompt)
        if not image_bytes:
            return "Failed to generate cartoon illustration."

        mime_type = "image/jpeg"
        filename = f"cartoon_{uuid.uuid4().hex[:8]}.jpg"

        if tool_context and hasattr(tool_context, "save_artifact"):
            try:
                artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
                if hasattr(res, "__await__"):
                    await res
            except Exception:
                pass

        try:
            storage_client = storage.Client(project=PROJECT_ID)
            bucket = storage_client.bucket(BUCKET_NAME)
            blob_name = f"story_cartoons/{filename}"
            blob = bucket.blob(blob_name)
            blob.upload_from_string(image_bytes, content_type=mime_type)
            return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
        except Exception as gcs_err:
            print(f"GCS Upload failed ({gcs_err}), attempting local static file fallback...")
            static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "cartoons")
            os.makedirs(static_dir, exist_ok=True)
            local_path = os.path.join(static_dir, filename)
            with open(local_path, "wb") as f:
                f.write(image_bytes)
            return f"/static/cartoons/{filename}"

    except Exception as e:
        return f"Error generating cartoon illustration: {str(e)}"

import asyncio

async def generate_comic_book_page(
    panel_prompts: list[str],
    tool_context: ToolContext = None,
) -> str:
    """Generates a single 1-page combined comic book image containing all 4 to 5 panel illustrations composite into one single image with card subtitles and character name tags.

    Args:
        panel_prompts: List of 4 to 5 scene descriptions for each comic panel step (e.g. ['Aarav putting on shoes with Mom Yamini', 'Aarav walking into dentist office', 'Aarav sitting in dentist chair', 'Aarav getting a star sticker']).
        tool_context: ADK ToolContext used to save artifact files to Playground.

    Returns:
        Public HTTPS URL of the 1 single combined composite comic book page image.
    """
    if not panel_prompts:
        return "No panel prompts provided."

    prompts = panel_prompts[:5]
    tasks = [_fetch_raw_panel_bytes(p) for p in prompts]
    raw_panel_bytes = await asyncio.gather(*tasks)

    composite_bytes = _composite_panels_to_single_image(raw_panel_bytes, panel_subtitles=prompts)
    if not composite_bytes:
        return "Failed to composite comic book page image."

    filename = f"comic_combined_{uuid.uuid4().hex[:8]}.jpg"
    mime_type = "image/jpeg"

    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part.from_bytes(data=composite_bytes, mime_type=mime_type)
            res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
            if hasattr(res, "__await__"):
                await res
        except Exception:
            pass

    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"story_cartoons/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(composite_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
    except Exception as gcs_err:
        print(f"GCS Upload failed ({gcs_err}), saving composite image to local static file fallback...")
        static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "cartoons")
        os.makedirs(static_dir, exist_ok=True)
        local_path = os.path.join(static_dir, filename)
        with open(local_path, "wb") as f:
            f.write(composite_bytes)
        return f"/static/cartoons/{filename}"
    if not composite_bytes:
        return "Failed to composite comic book page image."

    filename = f"comic_combined_{uuid.uuid4().hex[:8]}.jpg"
    mime_type = "image/jpeg"

    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part.from_bytes(data=composite_bytes, mime_type=mime_type)
            res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
            if hasattr(res, "__await__"):
                await res
        except Exception:
            pass

    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"story_cartoons/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(composite_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
    except Exception as gcs_err:
        print(f"GCS Upload failed ({gcs_err}), saving composite image to local static file fallback...")
        static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "cartoons")
        os.makedirs(static_dir, exist_ok=True)
        local_path = os.path.join(static_dir, filename)
        with open(local_path, "wb") as f:
            f.write(composite_bytes)
        return f"/static/cartoons/{filename}"

