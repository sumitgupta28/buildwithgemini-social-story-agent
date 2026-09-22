import os
import subprocess
from PIL import Image

def main():
    html_path = os.path.abspath("frontend/static/index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    img_url = "https://storage.googleapis.com/social-story-media-qwiklabs-gcp-02-1f7e291be017/story_cartoons/comic_combined_e21f9643.jpg"

    # Frame 1: Home Gallery View
    s1_html = html_content

    # Frame 2: Custom Story Creator Modal Open
    s2_html = html_content.replace(
        '<div class="modal" id="creator-modal">',
        '<div class="modal open" id="creator-modal">'
    ).replace(
        'id="custom-child" placeholder="Child\'s name (e.g. Aarav)"',
        'id="custom-child" value="Aarav"'
    ).replace(
        'id="custom-topic" placeholder="Story topic (e.g. Visiting dentist, Haircut)"',
        'id="custom-topic" value="Visiting the dentist with Mom Yamini"'
    ).replace(
        'id="custom-comfort" placeholder="Comfort item (e.g. Blue teddy bear)"',
        'id="custom-comfort" value="Blue teddy bear"'
    )

    # Frame 3: Lightbox Viewer Modal Open displaying subtitled comic page
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

    # Frame 4: Action Toast Saved to Google Photos
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

    p_images = []
    for h_name, p_name, content in states:
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
        # Quantize to adaptive 256 color palette for perfect GitHub GIF rendering
        p_img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        p_images.append(p_img)

    gif_path = "demo.gif"
    durations = [2500, 2500, 3500, 2500]  # ms per frame

    p_images[0].save(
        gif_path,
        save_all=True,
        append_images=p_images[1:],
        optimize=True,
        duration=durations,
        loop=0,
        disposal=2
    )

    print(f"GitHub-compatible animated demo.gif generated! Size: {os.path.getsize(gif_path)} bytes")

if __name__ == "__main__":
    main()
