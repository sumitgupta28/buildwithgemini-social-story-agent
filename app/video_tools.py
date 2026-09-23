import os
import io
import uuid
import asyncio
from PIL import Image, ImageDraw, ImageFont
import imageio.v3 as iio
from google.cloud import storage
from google.genai import types
from google.adk.tools import ToolContext
from app.image_tools import _fetch_raw_panel_bytes, _wrap_text

from app.app_utils.project_id import get_project_id

def _get_bucket_name() -> tuple[str, str]:
    project_id = get_project_id()
    bucket_name = os.environ.get("MEDIA_BUCKET_NAME", f"social-story-media-{project_id}")
    return project_id, bucket_name


async def generate_story_video(
    panel_prompts: list[str],
    story_title: str = "Aarav Going to the Dentist",
    tool_context: ToolContext = None,
) -> str:
    """Generates an animated 30-second H.264 MP4 video story slideshow with title intro and scene subtitles.

    Args:
        panel_prompts: List of scene prompts describing each story panel step.
        story_title: Heading title for the video story (e.g. 'Aarav Going to the Dentist').
        tool_context: ADK ToolContext used to save artifact files to Playground.

    Returns:
        Public HTTPS URL of the generated 30-second MP4 video story.
    """
    if not panel_prompts:
        return "No panel prompts provided."

    tasks = [_fetch_raw_panel_bytes(p) for p in panel_prompts]
    raw_panel_bytes = await asyncio.gather(*tasks)

    # Video specs: 1080x720, 10 fps, 30 seconds
    width, height = 1080, 720
    fps = 10
    total_sec = 30.0

    num_panels = len(raw_panel_bytes)
    intro_sec = 3.0
    panel_duration = (total_sec - intro_sec) / max(num_panels, 1)

    video_frames = []

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # 1. Title Intro Frame (3 seconds = 30 frames)
    intro_canvas = Image.new("RGB", (width, height), "#3a0ca3")
    idraw = ImageDraw.Draw(intro_canvas)
    idraw.text((width // 2, height // 2 - 40), "🎨 BUDDYCRAFT VISUAL SOCIAL STORY", fill="#4cc9f0", font=sub_font, anchor="mm")
    idraw.text((width // 2, height // 2 + 20), story_title.upper(), fill="#ffffff", font=title_font, anchor="mm")

    intro_arr = iio.imread(io.BytesIO(_img_to_bytes(intro_canvas)))
    for _ in range(int(intro_sec * fps)):
        video_frames.append(intro_arr)

    # 2. Panel Scene Frames
    for idx, raw_b in enumerate(raw_panel_bytes):
        panel_img = None
        if raw_b:
            try:
                panel_img = Image.open(io.BytesIO(raw_b)).convert("RGB")
            except Exception:
                pass

        if not panel_img:
            panel_img = Image.new("RGB", (840, 520), "#e2e8f0")

        # Create video frame canvas
        frame = Image.new("RGB", (width, height), "#0f172a")
        fdraw = ImageDraw.Draw(frame)

        # Header Title
        fdraw.rectangle([0, 0, width, 70], fill="#4361ee")
        fdraw.text((width // 2, 35), story_title.upper(), fill="#ffffff", font=sub_font, anchor="mm")

        # Resized panel artwork
        resized_panel = panel_img.resize((840, 520), Image.Resampling.LANCZOS)
        frame.paste(resized_panel, ((width - 840) // 2, 85))

        # Bottom Subtitle Banner
        fdraw.rectangle([0, 615, width, height], fill="#1e293b")
        sub_text = panel_prompts[idx].replace("*", "").strip() if idx < len(panel_prompts) else ""
        lines = _wrap_text(sub_text, max_chars=60)
        if len(lines) == 1:
            fdraw.text((width // 2, 660), lines[0], fill="#ffffff", font=sub_font, anchor="mm")
        elif len(lines) >= 2:
            fdraw.text((width // 2, 642), lines[0], fill="#ffffff", font=sub_font, anchor="mm")
            fdraw.text((width // 2, 678), lines[1], fill="#4cc9f0", font=sub_font, anchor="mm")

        # Speech bubble overlay on top half of video panel
        if ":" in sub_text or '"' in sub_text:
            dialogue_line = sub_text.split(":")[-1].replace('"', '').strip() if ":" in sub_text else sub_text
            fdraw.rounded_rectangle([150, 105, 450, 165], radius=12, fill="#ffffff", outline="#334155", width=3)
            fdraw.polygon([(170, 165), (160, 178), (185, 165)], fill="#ffffff")
            fdraw.line([(170, 165), (160, 178)], fill="#334155", width=3)
            fdraw.line([(160, 178), (185, 165)], fill="#334155", width=3)
            b_lines = _wrap_text(dialogue_line, max_chars=25)
            if len(b_lines) == 1:
                fdraw.text((300, 135), b_lines[0], fill="#1e293b", font=sub_font, anchor="mm")
            elif len(b_lines) >= 2:
                fdraw.text((300, 122), b_lines[0], fill="#1e293b", font=sub_font, anchor="mm")
                fdraw.text((300, 148), b_lines[1], fill="#1e293b", font=sub_font, anchor="mm")

        frame_arr = iio.imread(io.BytesIO(_img_to_bytes(frame)))
        repeat_count = int(panel_duration * fps)
        for _ in range(repeat_count):
            video_frames.append(frame_arr)

    # Pad or trim to ensure exactly 30 seconds (300 frames)
    target_frames = int(total_sec * fps)
    if len(video_frames) < target_frames:
        last_frame = video_frames[-1]
        while len(video_frames) < target_frames:
            video_frames.append(last_frame)
    elif len(video_frames) > target_frames:
        video_frames = video_frames[:target_frames]

    video_bytes = iio.imwrite("<bytes>", video_frames, extension=".mp4", fps=fps, codec="libx264")

    filename = f"story_video_{uuid.uuid4().hex[:8]}.mp4"
    mime_type = "video/mp4"

    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
            if hasattr(res, "__await__"):
                await res
        except Exception:
            pass

    try:
        project_id, bucket_name = _get_bucket_name()
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob_name = f"story_cartoons/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
    except Exception as gcs_err:
        print(f"GCS Video Upload failed ({gcs_err}), saving local static file fallback...")
        static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "cartoons")
        os.makedirs(static_dir, exist_ok=True)
        local_path = os.path.join(static_dir, filename)
        with open(local_path, "wb") as f:
            f.write(video_bytes)
        return f"/static/cartoons/{filename}"

def _img_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
