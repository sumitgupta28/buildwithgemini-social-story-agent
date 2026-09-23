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

def _load_font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in font_paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

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

    canvas_w = 1240
    margin = 24
    header_top = 24
    header_h = 130

    available_w = canvas_w - ((cols + 1) * margin)
    panel_w = available_w // cols  # ~584 px

    caption_h = 80
    img_h = int(panel_w * 0.76)  # ~444 px per panel illustration
    panel_h = img_h + caption_h  # ~524 px total panel height

    # Dynamically fit canvas height so there is ZERO extra empty white space at the bottom
    calc_canvas_h = (header_top + header_h) + margin + (rows * panel_h) + (rows * margin)
    canvas_h = calc_canvas_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), "#f8fafc")
    draw = ImageDraw.Draw(canvas)

    # Header Banner (Prominent Title Heading)
    header_title = story_title.strip().upper() if story_title else "BUDDYCRAFT VISUAL SOCIAL STORY"
    draw.rectangle([margin, header_top, canvas_w - margin, header_top + header_h], fill="#4361ee")
    
    title_font = _load_font(44, bold=True)
    caption_font = _load_font(20, bold=True)
    bubble_font = _load_font(17, bold=True)

    draw.text((canvas_w // 2, header_top + header_h // 2), header_title, fill="#ffffff", font=title_font, anchor="mm")

    start_y_offset = header_top + header_h + margin

    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        x = margin + c * (panel_w + margin)
        y = start_y_offset + r * (panel_h + margin)

        # Image section
        resized_img = img.resize((panel_w, img_h), Image.Resampling.LANCZOS)
        canvas.paste(resized_img, (x, y))

        # Render speech bubble overlay on top half of panel image
        if panel_subtitles and i < len(panel_subtitles):
            raw_sub = panel_subtitles[i].replace("*", "").replace("#", "").strip()
            dialogue_segments = []
            if "|" in raw_sub:
                parts = raw_sub.split("|")
                for p in parts[1:]:  # First part is scene caption, rest are dialogue lines
                    clean_p = p.strip()
                    if clean_p:
                        dialogue_segments.append(clean_p)
                if not dialogue_segments and ":" in raw_sub:
                    dialogue_segments.append(raw_sub.split(":", 1)[1].strip())
            elif ":" in raw_sub:
                dialogue_segments.append(raw_sub.split(":", 1)[1].strip())
            elif '"' in raw_sub:
                dialogue_segments.append(raw_sub)

            if dialogue_segments:
                for d_idx, d_text in enumerate(dialogue_segments[:2]):
                    side = "left" if d_idx == 0 else "right"
                    bx1 = x + 15 if side == "left" else x + panel_w - 280
                    by1 = y + 15 if side == "left" else y + 70
                    bx2 = bx1 + 265
                    by2 = by1 + 65
                    _draw_speech_bubble(draw, (bx1, by1, bx2, by2), d_text, bubble_font, tail_side=side)

        # Subtitle caption section
        cap_y = y + img_h
        draw.rectangle([x, cap_y, x + panel_w, y + panel_h], fill="#ffffff")
        draw.rectangle([x, y, x + panel_w, y + panel_h], outline="#3a0ca3", width=4)

        if panel_subtitles and i < len(panel_subtitles):
            raw_sub = panel_subtitles[i]
            clean_caption = raw_sub.split("|")[0].replace("*", "").replace("#", "").strip()
            lines = _wrap_text(clean_caption, max_chars=48)
            if len(lines) == 1:
                draw.text((x + panel_w // 2, cap_y + caption_h // 2), lines[0], fill="#1e293b", font=caption_font, anchor="mm")
            elif len(lines) >= 2:
                draw.text((x + panel_w // 2, cap_y + 26), lines[0], fill="#1e293b", font=caption_font, anchor="mm")
                draw.text((x + panel_w // 2, cap_y + 54), lines[1], fill="#1e293b", font=caption_font, anchor="mm")

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue()

def _draw_speech_bubble(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, tail_side: str = "left"):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=10, fill="#ffffff", outline="#334155", width=3)
    if tail_side == "left":
        tail = [(x1 + 12, y2), (x1 + 6, y2 + 10), (x1 + 24, y2)]
    else:
        tail = [(x2 - 24, y2), (x2 - 6, y2 + 10), (x2 - 12, y2)]
    draw.polygon(tail, fill="#ffffff")
    draw.line([tail[0], tail[1]], fill="#334155", width=3)
    draw.line([tail[1], tail[2]], fill="#334155", width=3)
    
    clean_text = text.replace('"', '').replace("'", "").strip()
    words = clean_text.split()
    lines = []
    curr = []
    for w in words:
        if sum(len(x) for x in curr) + len(w) + len(curr) > 20:
            lines.append(" ".join(curr))
            curr = [w]
        else:
            curr.append(w)
    if curr:
        lines.append(" ".join(curr))
    lines = lines[:3]
    
    line_h = 20
    start_y = y1 + ((y2 - y1) - len(lines) * line_h) // 2 + 2
    for idx, l in enumerate(lines):
        draw.text(((x1 + x2) // 2, start_y + idx * line_h), l, fill="#1e293b", font=font, anchor="mm")

async def _fetch_raw_panel_bytes(prompt: str) -> bytes:
    try:
        styled_prompt = (
            f"A soft 2D chibi cartoon storybook illustration for children. "
            f"Hand-drawn pencil lineart with soft pastel watercolor shading, muted warm color palette (soft sage greens, dusty teals, soft tan skin tones). "
            f"Light cream textured background. Expressive cute chibi character features. "
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
        except Exception as gcs_err:
            print(f"GCS Upload failed ({gcs_err}), using local static file fallback...")
            
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
    except Exception as gcs_err:
        print(f"GCS Upload failed ({gcs_err}), using local static file fallback...")

    return f"/static/cartoons/{filename}"




