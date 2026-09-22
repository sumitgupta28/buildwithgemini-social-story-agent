import pytest
from app.image_tools import generate_cartoon_illustration

@pytest.mark.asyncio
async def test_generate_cartoon_illustration():
    # Generate cartoon test
    url = await generate_cartoon_illustration(
        prompt="Aarav high fiving his teacher Ms. Priya at school"
    )
    assert url.startswith("https://storage.googleapis.com/") or "Error" not in url
