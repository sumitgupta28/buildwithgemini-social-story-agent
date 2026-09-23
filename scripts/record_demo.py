import os
import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

def record_demo():
    output_dir = "media"
    os.makedirs(output_dir, exist_ok=True)
    raw_video_dir = os.path.join(output_dir, "raw_videos")
    os.makedirs(raw_video_dir, exist_ok=True)

    print("🚀 Starting Playwright browser automation for scenario demo recording...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=raw_video_dir,
            record_video_size={"width": 1280, "height": 800}
        )
        page = context.new_page()

        print("🌐 Navigating to http://localhost:8080...")
        page.goto("http://localhost:8080")
        page.wait_for_selector(".scenario-card", timeout=15000)
        time.sleep(2)

        print("📖 Clicking 'View Story' on Dentist Visit scenario...")
        # Find Dentist Visit card and click View Story button
        dentist_card = page.locator(".scenario-card", has_text="Dentist Visit")
        view_btn = dentist_card.locator("button", has_text="View Story")
        view_btn.click()
        page.wait_for_selector("#viewer-modal.open", timeout=10000)
        time.sleep(3) # Pause to inspect read-only social story steps

        print("🎨 Triggering 'Generate Visual Comic Page'...")
        gen_img_btn = page.locator("button", has_text="Generate Visual Comic Page")
        gen_img_btn.click()

        print("⏳ Waiting for visual comic image generation...")
        page.wait_for_selector("#zoomable-story-img", timeout=45000)
        time.sleep(2)

        print("🔍 Testing Zoom In, Zoom Out & Reset controls...")
        zoom_in_btn = page.locator("button[onclick='zoomInImage()']")
        zoom_out_btn = page.locator("button[onclick='zoomOutImage()']")
        reset_btn = page.locator("button[onclick='resetZoomImage()']")

        # Zoom In 3 times
        for _ in range(3):
            zoom_in_btn.click()
            time.sleep(0.8)

        # Scroll to inspect panels
        viewer_body = page.locator("#viewer-body")
        viewer_body.evaluate("el => el.scrollTop = 200")
        time.sleep(1)
        viewer_body.evaluate("el => el.scrollTop = 400")
        time.sleep(1)
        viewer_body.evaluate("el => el.scrollTop = 0")
        time.sleep(1)

        # Zoom Out twice
        zoom_out_btn.click()
        time.sleep(0.8)
        zoom_out_btn.click()
        time.sleep(0.8)

        # Reset zoom
        reset_btn.click()
        time.sleep(1.5)

        print("🎥 Clicking 'Generate Video'...")
        gen_vid_btn = page.locator("#post-gen-actions button", has_text="Back to Story Text")
        # Go back to story text or click Generate Video directly
        gen_vid_btn.click()
        time.sleep(1.5)

        gen_vid_action = page.locator("button", has_text="Generate Video")
        gen_vid_action.click()

        print("⏳ Waiting for 30s Animated Video Story rendering...")
        page.wait_for_selector("video.modal-story-img", timeout=60000)
        print("▶️ Video generated and playing!")
        time.sleep(8) # Let video play

        # Get video path BEFORE closing page/context
        video_obj = page.video
        video_path = video_obj.path() if video_obj else None
        
        context.close()
        browser.close()

    if not video_path or not os.path.exists(video_path):
        # Fallback to finding latest webm file in raw_videos
        webm_files = [os.path.join(raw_video_dir, f) for f in os.listdir(raw_video_dir) if f.endswith('.webm')]
        if webm_files:
            video_path = max(webm_files, key=os.path.getmtime)

    print(f"📹 Raw recording saved to: {video_path}")

    # Output paths
    docs_dir = "docs"
    os.makedirs(docs_dir, exist_ok=True)

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    gif_paths = [os.path.join(output_dir, "demo_story.gif"), os.path.join(docs_dir, "demo.gif")]
    mp4_paths = [os.path.join(output_dir, "demo_story.mp4"), os.path.join(docs_dir, "demo.mp4")]

    for gif_path in gif_paths:
        print(f"⚙️ Converting raw recording to speeded-up GIF ({gif_path}) via ffmpeg...")
        cmd_gif = [
            ffmpeg_exe, "-y", "-i", video_path,
            "-vf", "setpts=0.6*PTS,fps=12,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer",
            gif_path
        ]
        subprocess.run(cmd_gif, check=True)

    for mp4_path in mp4_paths:
        print(f"⚙️ Converting raw recording to MP4 ({mp4_path}) via ffmpeg...")
        cmd_mp4 = [
            ffmpeg_exe, "-y", "-i", video_path,
            "-vf", "setpts=0.6*PTS,scale=1000:-2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            mp4_path
        ]
        subprocess.run(cmd_mp4, check=True)

    print("✅ All demo GIF and MP4 files created successfully!")

if __name__ == "__main__":
    record_demo()
