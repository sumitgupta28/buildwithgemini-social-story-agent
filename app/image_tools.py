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
    return "qwiklabs-gcp-01-eb84874d9448"

PROJECT_ID = _get_project_id()
BUCKET_NAME = os.environ.get("MEDIA_BUCKET_NAME", f"social-story-media-{PROJECT_ID}")


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

def _composite_panels_to_single_image(
    raw_panel_bytes: list[bytes],
    panel_subtitles: list[str] = None,
    story_title: str = ""
) -> bytes:
    images = []
    for idx, b in enumerate(raw_panel_bytes):
        img = None
        if b:
            try:
                img = Image.open(io.BytesIO(b)).convert("RGB")
            except Exception as err:
                print(f"Failed to parse panel image bytes: {err}")
        if not img:
            img = Image.new("RGB", (600, 420), color="#e2e8f0")
            d = ImageDraw.Draw(img)
            d.rectangle([10, 10, 590, 410], outline="#94a3b8", width=3)
            d.rectangle([30, 30, 570, 390], fill="#f1f5f9")
            sub_text = panel_subtitles[idx] if (panel_subtitles and idx < len(panel_subtitles)) else f"Step {idx+1}"
            sub_clean = sub_text.replace("*", "").replace("#", "").strip()
            try:
                font_card = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            except Exception:
                font_card = ImageFont.load_default()
            d.text((300, 210), f"🎨 {sub_clean[:35]}", fill="#334155", font=font_card, anchor="mm")
        images.append(img)

    if not images:
        return None

    num_panels = len(images)
    cols = 2
    rows = math.ceil(num_panels / cols)

    # Standard A4 Canvas Dimensions (1240 x 1754 px, aspect ratio ~ 1:1.414)
    canvas_w = 1240
    header_h = 110
    footer_h = 20
    margin = 24

    available_w = canvas_w - ((cols + 1) * margin)
    panel_w = available_w // cols  # ~584 px

    min_canvas_h = int(canvas_w * 1.414)  # ~1753 px
    caption_h = 75
    calc_panel_h = int(panel_w * 0.7) + caption_h  # ~480 px
    calc_canvas_h = header_h + (rows * calc_panel_h) + ((rows + 1) * margin) + footer_h
    canvas_h = max(min_canvas_h, calc_canvas_h)

    img_h = calc_panel_h - caption_h
    panel_h = calc_panel_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), "#f8fafc")
    draw = ImageDraw.Draw(canvas)

    # Header Banner (A4 Top Title Heading)
    header_title = story_title.strip().upper() if story_title else "BUDDYCRAFT VISUAL SOCIAL STORY"
    draw.rectangle([margin, margin, canvas_w - margin, header_h], fill="#4361ee")
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    draw.text((canvas_w // 2, margin + 45), header_title, fill="#ffffff", font=title_font, anchor="mm")

    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        x = margin + c * (panel_w + margin)
        y = header_h + margin + r * (panel_h + margin)

        # Image section
        resized_img = img.resize((panel_w, img_h), Image.Resampling.LANCZOS)
        canvas.paste(resized_img, (x, y))

        # Subtitle caption section
        cap_y = y + img_h
        draw.rectangle([x, cap_y, x + panel_w, y + panel_h], fill="#ffffff")
        draw.rectangle([x, y, x + panel_w, y + panel_h], outline="#3a0ca3", width=4)

        if panel_subtitles and i < len(panel_subtitles):
            raw_sub = panel_subtitles[i]
            clean_sub = raw_sub.replace("*", "").replace("#", "").strip()
            lines = _wrap_text(clean_sub, max_chars=52)
            if len(lines) == 1:
                draw.text((x + panel_w // 2, cap_y + caption_h // 2), lines[0], fill="#1e293b", font=sub_font, anchor="mm")
            elif len(lines) >= 2:
                draw.text((x + panel_w // 2, cap_y + 24), lines[0], fill="#1e293b", font=sub_font, anchor="mm")
                draw.text((x + panel_w // 2, cap_y + 50), lines[1], fill="#1e293b", font=sub_font, anchor="mm")

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
            static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "cartoons")
            os.makedirs(static_dir, exist_ok=True)
            local_path = os.path.join(static_dir, filename)
            with open(local_path, "wb") as f:
                f.write(image_bytes)
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
            return f"/static/cartoons/{filename}"

    except Exception as e:
        return f"Error generating cartoon illustration: {str(e)}"

import asyncio

async def generate_comic_book_page(
    panel_prompts: list[str],
    story_title: str = "",
    tool_context: ToolContext = None,
) -> str:
    """Generates a single print-ready A4 combined comic book page image containing all panel illustrations composite into one image with top title heading and card subtitles.

    Args:
        panel_prompts: List of scene descriptions for each comic panel step (e.g. ['Aarav putting on shoes with Mom Yamini', 'Aarav walking into dentist office', 'Aarav sitting in dentist chair', 'Aarav getting a star sticker']).
        story_title: Custom top title heading for the A4 comic page (e.g. 'Aarav Going to the Dentist').
        tool_context: ADK ToolContext used to save artifact files to Playground.

    Returns:
        Public HTTPS URL of the 1 single combined composite A4 comic book page image.
    """
    if not panel_prompts:
        return "No panel prompts provided."

    prompts = list(panel_prompts)
    tasks = [_fetch_raw_panel_bytes(p) for p in prompts]
    raw_panel_bytes = await asyncio.gather(*tasks)

    composite_bytes = _composite_panels_to_single_image(raw_panel_bytes, panel_subtitles=prompts, story_title=story_title)
    if not composite_bytes:
        return "Failed to generate image for given Story."


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
        static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "cartoons")
        os.makedirs(static_dir, exist_ok=True)
        local_path = os.path.join(static_dir, filename)
        with open(local_path, "wb") as f:
            f.write(composite_bytes)
    except Exception as local_err:
        print(f"Local static file write error: {local_err}")

    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"story_cartoons/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(composite_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
    except Exception as gcs_err:
        print(f"GCS Upload failed ({gcs_err}), saving composite image to local static file fallback...")
        return f"/static/cartoons/{filename}"



