import pytest
from app.video_tools import generate_story_video
import os

@pytest.mark.asyncio
async def test_generate_story_video_file():
    prompts = [
        "Aarav putting on shoes with Mom Yamini",
        "Aarav walking into dentist office",
        "Aarav sitting in dentist chair",
        "Aarav getting a star sticker"
    ]
    title = "Aarav Going to the Dentist"
    
    url = await generate_story_video(prompts, story_title=title)
    assert url is not None
    assert ("http" in url or "/static/cartoons/" in url)
