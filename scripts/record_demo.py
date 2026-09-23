# Copyright 2026 Google LLC
# Automated demo video & GIF recorder for Social Story Agent

import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

async def record_demo():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs_temp"))
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=temp_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print("🎬 [1/4] Navigating to local Social Story Agent web app...")
        await page.goto("http://127.0.0.1:8080", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Turn 1: Scenario 1 - Visual Story Page (4-Panel Comic Generation)
        print("🎨 [2/4] Turn 1: Opening Scenario Card & Generating 4-Panel Comic...")
        card_btn = page.locator(".card-btn").first
        await card_btn.wait_for(state="visible", timeout=10000)
        await card_btn.click()

        # Wait for viewer modal to open and render composite comic image
        await page.wait_for_selector("#viewer-modal.open", timeout=60000)
        await page.wait_for_selector(".modal-story-img", timeout=90000)
        print("   ✅ Turn 1 Complete: 4-Panel Comic Lightbox rendered.")
        await page.wait_for_timeout(4000)

        # Turn 2: Scenario 2 - 30-Second Animated Video Story Generation
        print("🎥 [3/4] Turn 2: Generating 30s Animated Video Story...")
        video_btn = page.locator("#video-story-btn")
        if await video_btn.is_visible():
            await video_btn.click()
            await page.wait_for_selector("video", timeout=120000)
            print("   ✅ Turn 2 Complete: 30s Animated Video Story rendered.")
            await page.wait_for_timeout(8000)
        else:
            print("   ⚠️ #video-story-btn not visible, pausing on comic lightbox...")
            await page.wait_for_timeout(4000)

        # Flush and retrieve video path cleanly
        video_path = await page.video.path()
        await context.close()
        await browser.close()

    print(f"   📹 Raw WebM recording saved: {video_path}")
    mp4_path = os.path.join(output_dir, "demo.mp4")
    gif_path = os.path.join(output_dir, "demo.gif")

    print(f"⚙️ [4/4] Converting raw recording to MP4 and GIF...")
    
    # 1. Convert to MP4
    cmd_mp4 = [
        "ffmpeg", "-y", "-i", video_path,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        mp4_path
    ]
    subprocess.run(cmd_mp4, check=True)
    print(f"   🎥 Saved MP4: {mp4_path}")

    # 2. Convert to high-quality GIF (15 fps, 800px scale, ~25-35 seconds)
    cmd_gif = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", "fps=15,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        gif_path
    ]
    subprocess.run(cmd_gif, check=True)
    print(f"   🖼️ Saved GIF: {gif_path}")

    # Clean up temp webm
    try:
        os.remove(video_path)
    except Exception:
        pass
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

    print("🎉 Recording & conversion completed successfully!")

if __name__ == "__main__":
    asyncio.run(record_demo())
