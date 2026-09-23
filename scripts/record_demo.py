import os
import asyncio
import subprocess
from PIL import Image
import imageio.v3 as iio
from playwright.async_api import async_playwright

async def record_demo():
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs_temp"))
    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=temp_dir,
            record_video_size={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print("🎬 [1/4] Navigating to Social Story Agent web app...")
        await page.goto("http://127.0.0.1:8080", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # -------------------------------------------------------------
        # SCENARIO 1: Dentist Visit
        # -------------------------------------------------------------
        print("🦷 [2/4] SCENARIO 1: Dentist Visit - Generating Comic Page...")
        cards = page.locator(".scenario-card")
        count = await cards.count()
        dentist_btn = None
        bus_btn = None

        for i in range(count):
            text = await cards.nth(i).inner_text()
            if "Dentist" in text:
                dentist_btn = cards.nth(i).locator(".card-btn")
            elif "School Bus" in text or "Bus" in text:
                bus_btn = cards.nth(i).locator(".card-btn")

        if not dentist_btn:
            dentist_btn = page.locator(".card-btn").first

        await dentist_btn.click()

        # Wait for comic image generation
        await page.wait_for_selector("#viewer-modal.open", timeout=60000)
        await page.wait_for_selector(".modal-story-img", timeout=90000)
        print("   ✅ Dentist Visit Comic generated.")
        await page.wait_for_timeout(2000)

        # ZOOM into comic image section to clearly show dialogue panels & clothing names
        print("   🔍 Zooming into Dentist Visit image sections...")
        await page.evaluate("""() => {
            const img = document.querySelector('.modal-story-img');
            const modalBody = document.querySelector('.modal-body');
            if (img && modalBody) {
                img.style.transition = 'transform 0.8s ease-in-out';
                modalBody.style.overflow = 'hidden';
            }
        }""")

        # Zoom Top Left (Panel 1)
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1.8) translate(20%, 20%)'; }")
        await page.wait_for_timeout(2500)

        # Zoom Top Right (Panel 2)
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1.8) translate(-20%, 20%)'; }")
        await page.wait_for_timeout(2500)

        # Zoom Bottom Left (Panel 3)
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1.8) translate(20%, -20%)'; }")
        await page.wait_for_timeout(2500)

        # Reset Zoom to Full Page
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1) translate(0, 0)'; }")
        await page.wait_for_timeout(2000)

        # Generate Video for Dentist Visit
        print("   🎥 Generating Dentist Visit 30s Video Story...")
        video_btn = page.locator("#video-story-btn")
        await video_btn.click()
        await page.wait_for_selector("video", timeout=120000)
        print("   ✅ Dentist Visit Video rendered.")
        await page.wait_for_timeout(5000)

        # Close Viewer Modal
        close_btn = page.locator(".modal-close").first
        await close_btn.click()
        await page.wait_for_timeout(1500)

        # -------------------------------------------------------------
        # SCENARIO 2: Riding the School Bus
        # -------------------------------------------------------------
        print("🚌 [3/4] SCENARIO 2: Riding the School Bus - Generating Comic Page...")
        if not bus_btn:
            bus_btn = page.locator(".card-btn").nth(1)

        await bus_btn.click()

        # Wait for comic image generation
        await page.wait_for_selector("#viewer-modal.open", timeout=60000)
        await page.wait_for_selector(".modal-story-img", timeout=90000)
        print("   ✅ School Bus Comic generated.")
        await page.wait_for_timeout(2000)

        # ZOOM into School Bus comic image section
        print("   🔍 Zooming into School Bus image sections...")
        await page.evaluate("""() => {
            const img = document.querySelector('.modal-story-img');
            const modalBody = document.querySelector('.modal-body');
            if (img && modalBody) {
                img.style.transition = 'transform 0.8s ease-in-out';
                modalBody.style.overflow = 'hidden';
            }
        }""")

        # Zoom Top Left (Panel 1)
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1.8) translate(20%, 20%)'; }")
        await page.wait_for_timeout(2500)

        # Zoom Bottom Left (Panel 3)
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1.8) translate(20%, -20%)'; }")
        await page.wait_for_timeout(2500)

        # Reset Zoom to Full Page
        await page.evaluate("() => { document.querySelector('.modal-story-img').style.transform = 'scale(1) translate(0, 0)'; }")
        await page.wait_for_timeout(2000)

        # Generate Video for School Bus
        print("   🎥 Generating School Bus 30s Video Story...")
        video_btn = page.locator("#video-story-btn")
        await video_btn.click()
        await page.wait_for_selector("video", timeout=120000)
        print("   ✅ School Bus Video rendered.")
        await page.wait_for_timeout(6000)

        # Retrieve video path
        video_path = await page.video.path()
        await context.close()
        await browser.close()

    print(f"📹 Raw WebM recording saved: {video_path}")
    gif_path = os.path.join(docs_dir, "demo.gif")

    print(f"⚙️ [4/4] Processing WebM frames with Python PIL (speedup & optimized GIF palette)...")
    raw_frames = iio.imread(video_path)
    total_frames = len(raw_frames)
    print(f"   Fetched {total_frames} total frames from recording.")

    # Sample every 8th frame (fast playback speedup)
    step = 8
    sampled_images = []
    target_width = 720

    for idx in range(0, total_frames, step):
        frame_arr = raw_frames[idx]
        img = Image.fromarray(frame_arr)
        w, h = img.size
        new_h = int(h * (target_width / float(w)))
        img_resized = img.resize((target_width, new_h), Image.Resampling.LANCZOS)
        img_quantized = img_resized.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        sampled_images.append(img_quantized)

    print(f"   Saving {len(sampled_images)} frames to high-quality {gif_path}...")
    sampled_images[0].save(
        gif_path,
        save_all=True,
        append_images=sampled_images[1:],
        optimize=True,
        duration=90,
        loop=0,
        disposal=2
    )

    print(f"🎉 Saved GIF: {gif_path} ({os.path.getsize(gif_path)} bytes)")

    # Cleanup temp webm
    try:
        os.remove(video_path)
    except Exception:
        pass

    print("🎉 Demo recording and GIF generation completed successfully!")

if __name__ == "__main__":
    asyncio.run(record_demo())
