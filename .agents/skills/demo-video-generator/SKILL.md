---
name: demo-video-generator
description: Automated Playwright browser demo recorder and GIF generator for BuddyCraft social story studio scenarios. Use when the user requests generating a demo video/GIF for README.md.
---

# Demo Video & GIF Generator Skill

This skill provides an automated pipeline using Playwright and ffmpeg to record visual social story studio scenarios, speed up progress bars during image/video generation, convert recordings to optimized GIFs, and update the repository `README.md`.

## Workflow Steps

1. **Verify Local Server**:
   Ensure local server is active at `http://localhost:8080`.

2. **Execute Recording Script**:
   Run the Playwright automation script to navigate the UI:
   - Load dashboard (`http://localhost:8080`)
   - Click "View Story" on target scenario (e.g. Dentist Visit)
   - Inspect Read-Only Carol Gray social story steps
   - Click "🎨 Generate Visual Comic Page"
   - Wait for image generation completion
   - Click Zoom In (+), Zoom Out (-), and Reset buttons to inspect all panels
   - Click "🎥 Generate Video" and wait for rendering
   - Play video

3. **Convert and Speed-up via ffmpeg**:
   - Apply video speed-up filter during loading progress phases.
   - Convert to high-quality compressed GIF (`media/demo_story.gif`).

4. **Update README.md & Git Commit**:
   - Embed `![BuddyCraft Social Story Demo](media/demo_story.gif)` into `README.md`.
   - Commit and push to Git.

## Automation Script

Use `python scripts/record_demo.py` to perform the entire recording automatically.
