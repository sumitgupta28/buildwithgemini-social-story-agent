import pytest
from app.image_tools import generate_cartoon_illustration

@pytest.mark.asyncio
async def test_generate_cartoon_illustration():
    # Generate cartoon test
    url = await generate_cartoon_illustration(
        prompt="Aarav high fiving his teacher Ms. Priya at school"
    )
    assert url.startswith("https://storage.googleapis.com/") or "Error" not in url

from app.image_tools import generate_comic_book_page

@pytest.mark.asyncio
async def test_generate_comic_book_page():
    panels = await generate_comic_book_page([
        "Aarav packing school bag with Mom Yamini",
        "Aarav sitting on bus",
        "Aarav high fiving teacher Ms. Priya",
        "Aarav getting a star sticker",
    ])
    assert len(panels) == 4
    assert panels[0]["panel"] == 1
    assert "image_url" in panels[0]

