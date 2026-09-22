import pytest
from app.image_tools import generate_cartoon_illustration, generate_comic_book_page, _composite_panels_to_single_image
from PIL import Image
import io

@pytest.mark.asyncio
async def test_composite_panels_to_single_image_a4():
    # Test compositing 6 panels into A4 image with custom story title heading
    sample_img = Image.new("RGB", (300, 200), "#4361ee")
    buf = io.BytesIO()
    sample_img.save(buf, format="JPEG")
    b = buf.getvalue()

    raw_bytes = [b] * 6
    subtitles = [f"Step {i+1} subtitle detail" for i in range(6)]
    title = "Aarav Going to the Dentist"

    composite_bytes = _composite_panels_to_single_image(raw_bytes, panel_subtitles=subtitles, story_title=title)
    assert composite_bytes is not None

    res_img = Image.open(io.BytesIO(composite_bytes))
    w, h = res_img.size
    # Verify A4 aspect ratio (h / w >= 1.35)
    assert h / w >= 1.35
