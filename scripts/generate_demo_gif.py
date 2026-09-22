import os
import subprocess
from PIL import Image

def main():
    html_path = os.path.abspath("frontend/static/index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    img_url = "https://storage.googleapis.com/social-story-media-qwiklabs-gcp-02-1f7e291be017/story_cartoons/comic_combined_e21f9643.jpg"

    # State 1: Gallery Default View
    s1_html = html_content

    # State 2: Custom Creator Modal Open
    s2_html = html_content.replace(
        '<div class="modal" id="creator-modal">',
        '<div class="modal open" id="creator-modal">'
    )

    # State 3: Lightbox Viewer Modal Open
    s3_html = html_content.replace(
        '<div class="modal" id="viewer-modal">',
        '<div class="modal open" id="viewer-modal">'
    ).replace(
        '<h3 id="viewer-title">Story Preview</h3>',
        '<h3 id="viewer-title">Aarav\'s Dentist Adventure with Mom Yamini</h3>'
    ).replace(
        '<img id="viewer-img" src="" alt="Social Story Image">',
        f'<img id="viewer-img" src="{img_url}" alt="Social Story Image">'
    )

    # State 4: Saved to Google Photos Toast Action
    s4_html = s3_html.replace(
        '<div class="toast" id="toast"></div>',
        '<div class="toast show" id="toast">📷 Saved to Google Photos!</div>'
    )

    states = [
        ("s1.html", "/tmp/frame1.png", s1_html),
        ("s2.html", "/tmp/frame2.png", s2_html),
        ("s3.html", "/tmp/frame3.png", s3_html),
        ("s4.html", "/tmp/frame4.png", s4_html),
    ]

    frames = []
    for h_name, p_name, content in states:
        h_file = os.path.join("/tmp", h_name)
        with open(h_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        cmd = [
            "google-chrome", "--headless", "--no-sandbox", "--disable-gpu",
            "--window-size=1200,850",
            f"--screenshot={p_name}",
            f"file://{h_file}"
        ]
        subprocess.run(cmd, check=True)
        img = Image.open(p_name).convert("RGB")
        frames.append(img)

    gif_path = "demo.gif"
    durations = [2500, 2000, 3000, 2500]  # ms per frame
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0
    )
    print(f"New demo.gif generated successfully! File size: {os.path.getsize(gif_path)} bytes")

if __name__ == "__main__":
    main()
