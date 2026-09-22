import os
import subprocess
from PIL import Image
import imageio.v3 as iio

def main():
    html_path = os.path.abspath("frontend/static/index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    img_url_dentist = "https://storage.googleapis.com/social-story-media-qwiklabs-gcp-02-1f7e291be017/story_cartoons/comic_combined_e21f9643.jpg"
    img_url_swim = "https://storage.googleapis.com/social-story-media-qwiklabs-gcp-02-1f7e291be017/story_cartoons/comic_combined_e21f9643.jpg"

    # Turn 1: Existing Scenario (Dentist Visit)
    # Frame 1: Home Gallery View
    f1_html = html_content

    # Frame 2: Lightbox Loading Spinner for Dentist Visit
    f2_html = html_content.replace(
        '<div class="modal-overlay" id="viewer-modal">',
        '<div class="modal-overlay open" id="viewer-modal">'
    ).replace(
        '<h2 id="viewer-title">Visual Social Story Page</h2>',
        '<h2 id="viewer-title">Aarav\'s Dentist Visit</h2>'
    ).replace(
        '<!-- Image or Loader -->',
        '<div class="loader"><div class="spinner"></div><p>🎨 Composite 1-Page Comic Story generating...</p></div>'
    )

    # Frame 3: Lightbox Viewer showing generated 4-panel composite comic story
    f3_html = html_content.replace(
        '<div class="modal-overlay" id="viewer-modal">',
        '<div class="modal-overlay open" id="viewer-modal">'
    ).replace(
        '<h2 id="viewer-title">Visual Social Story Page</h2>',
        '<h2 id="viewer-title">Aarav\'s Dentist Visit</h2>'
    ).replace(
        '<!-- Image or Loader -->',
        f'<img src="{img_url_dentist}" class="modal-story-img" alt="Dentist Visit">'
    )

    # Turn 2: New Custom Scenario Creation & Save
    # Frame 4: Custom Creator Modal Open with filled inputs
    f4_html = html_content.replace(
        '<div class="modal-overlay creator-modal" id="creator-modal">',
        '<div class="modal-overlay creator-modal open" id="creator-modal">'
    ).replace(
        'value="Aarav"',
        'value="Aarav"'
    ).replace(
        'placeholder="e.g. Visiting the dentist with Mom Yamini"',
        'value="First Day at Swimming Class"'
    ).replace(
        'value="Blue teddy bear"',
        'value="Goggles & Floating Ring"'
    )

    # Frame 5: New scenario card added to top of gallery grid
    new_card_html = '''
      <div class="scenario-card">
        <div>
          <div class="card-header">
            <div class="card-icon">✂️</div>
            <div class="card-title-text">
              <h3>Aarav's First Day at Swimming Class</h3>
              <span class="card-badge">routines</span>
            </div>
          </div>
          <p class="card-desc">First Day at Swimming Class for Aarav with Goggles & Floating Ring for sensory comfort.</p>
        </div>
        <div class="card-footer">
          <button class="card-btn">
            <span class="material-symbols-outlined">auto_awesome</span>
            View Story Page
          </button>
        </div>
      </div>
    '''
    f5_html = html_content.replace(
        '<div class="gallery-grid" id="gallery-grid">',
        f'<div class="gallery-grid" id="gallery-grid">{new_card_html}'
    )

    # Frame 6: Lightbox Viewer for new custom swimming story
    f6_html = f5_html.replace(
        '<div class="modal-overlay" id="viewer-modal">',
        '<div class="modal-overlay open" id="viewer-modal">'
    ).replace(
        '<h2 id="viewer-title">Visual Social Story Page</h2>',
        '<h2 id="viewer-title">Aarav\'s First Day at Swimming Class</h2>'
    ).replace(
        '<!-- Image or Loader -->',
        f'<img src="{img_url_swim}" class="modal-story-img" alt="Swimming Class">'
    )

    # Frame 7: Action Toast Notification Saved to Google Photos
    f7_html = f6_html.replace(
        '<div class="toast" id="toast">Notification</div>',
        '<div class="toast show" id="toast">📷 Saved to Google Photos!</div>'
    )

    frames_data = [
        ("f1.html", "/tmp/f1.png", f1_html, 2000),
        ("f2.html", "/tmp/f2.png", f2_html, 1500),
        ("f3.html", "/tmp/f3.png", f3_html, 3000),
        ("f4.html", "/tmp/f4.png", f4_html, 2500),
        ("f5.html", "/tmp/f5.png", f5_html, 2000),
        ("f6.html", "/tmp/f6.png", f6_html, 3000),
        ("f7.html", "/tmp/f7.png", f7_html, 2500),
    ]

    p_images = []
    durations = []
    png_paths = []

    for h_name, p_name, content, dur in frames_data:
        h_file = os.path.join("/tmp", h_name)
        with open(h_file, "w", encoding="utf-8") as f:
            f.write(content)

        cmd = [
            "google-chrome", "--headless", "--no-sandbox", "--disable-gpu",
            "--window-size=1000,650",
            f"--screenshot={p_name}",
            f"file://{h_file}"
        ]
        subprocess.run(cmd, check=True)
        
        img = Image.open(p_name).convert("RGB")
        p_img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        p_images.append(p_img)
        durations.append(dur)
        png_paths.append(p_name)

    # 1. Save demo.gif
    gif_path = "demo.gif"
    p_images[0].save(
        gif_path,
        save_all=True,
        append_images=p_images[1:],
        optimize=True,
        duration=durations,
        loop=0,
        disposal=2
    )
    print(f"✅ demo.gif created! Size: {os.path.getsize(gif_path)} bytes")

    # 2. Save demo_video.mp4
    video_path = "demo_video.mp4"
    video_frames = []
    fps = 10
    
    for idx, png_p in enumerate(png_paths):
        dur_sec = durations[idx] / 1000.0
        num_repeat = int(dur_sec * fps)
        frame_array = iio.imread(png_p)
        for _ in range(num_repeat):
            video_frames.append(frame_array)

    iio.imwrite(video_path, video_frames, fps=fps, codec="libx264")
    print(f"✅ demo_video.mp4 created! Size: {os.path.getsize(video_path)} bytes")

if __name__ == "__main__":
    main()
