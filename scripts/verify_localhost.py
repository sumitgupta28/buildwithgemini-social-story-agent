#!/usr/bin/env python3
"""
scripts/verify_localhost.py
End-to-End Localhost Application Verification Script.

Validates all localhost API endpoints, static assets, HEAD/GET cartoon proxies,
and /chat social story generation end-to-end before pushing code to remote repo.
"""

import sys
import re
import requests

BASE_URL = "http://localhost:8080"

def log(msg, success=True):
    symbol = "✅" if success else "❌"
    print(f"{symbol} {msg}")

def ensure_server_running():
    try:
        r = requests.get(f"{BASE_URL}/api/config", timeout=2)
        if r.status_code == 200:
            return None
    except Exception:
        pass

    import subprocess, time
    print("⏳ Starting local frontend server on port 8080...")
    proc = subprocess.Popen([sys.executable, "frontend/main.py"])
    for _ in range(30):
        time.sleep(1)
        try:
            r = requests.get(f"{BASE_URL}/api/config", timeout=2)
            if r.status_code == 200:
                print("✅ Frontend server on port 8080 is ready!")
                return proc
        except Exception:
            pass
    raise RuntimeError("Failed to start frontend server on port 8080")

def test_endpoints():
    print("\n==========================================")
    print("🚀 Running Localhost End-to-End Verification")
    print("==========================================\n")
    
    server_proc = ensure_server_running()

    # 1. Test GET /
    try:
        r = requests.get(f"{BASE_URL}/", timeout=10)
        assert r.status_code == 200, f"Status code: {r.status_code}"
        assert "<title>" in r.text, "Index HTML missing title tag"
        log("GET / (Frontend Web UI is loaded)")
    except Exception as e:
        log(f"GET / failed: {e}", success=False)
        sys.exit(1)


    # 2. Test GET /api/config
    try:
        r = requests.get(f"{BASE_URL}/api/config", timeout=10)
        assert r.status_code == 200, f"Status code: {r.status_code}"
        log("GET /api/config (OAuth client config returned)")
    except Exception as e:
        log(f"GET /api/config failed: {e}", success=False)
        sys.exit(1)

    # 3. Test GET /api/scenarios
    try:
        r = requests.get(f"{BASE_URL}/api/scenarios", timeout=10)
        assert r.status_code == 200, f"Status code: {r.status_code}"
        data = r.json()
        assert isinstance(data, list) and len(data) >= 6, "Expected at least 6 scenarios"
        log(f"GET /api/scenarios (Fetched {len(data)} scenario cards)")
    except Exception as e:
        log(f"GET /api/scenarios failed: {e}", success=False)
        sys.exit(1)

    # 4. Test POST /chat end-to-end story generation
    try:
        import uuid
        test_uid = f"verify-user-{uuid.uuid4().hex[:8]}"
        print(f"\n⏳ Testing POST /chat with story request for session {test_uid}...")
        chat_body = {
            "user_id": test_uid,
            "message": "Please generate a 4-panel comic book page social story for Aarav visiting the dentist with Mom Yamini."
        }
        r = requests.post(f"{BASE_URL}/chat", json=chat_body, timeout=120)

        assert r.status_code == 200, f"Chat status code: {r.status_code}"
        response_data = r.json()
        parts = response_data.get("parts", [])
        reply_text = "\n".join([p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")])
        assert reply_text, f"Response parts empty or invalid: {response_data}"

        log("POST /chat (Social story generated successfully)")
        print(f"DEBUG Reply text length: {len(reply_text)} content snippet: {reply_text[:300]}")


        # Extract image URL from response text (relative or full URL)
        img_match = re.search(r'(/static/cartoons/[a-zA-Z0-9_\-\.]+\.(?:jpg|jpeg|png))', reply_text)
        if not img_match:
            img_match = re.search(r'https?://[^/]+(/static/cartoons/[a-zA-Z0-9_\-\.]+\.(?:jpg|jpeg|png))', reply_text)
        
        if img_match:
            img_path = img_match.group(1)
            img_url = f"{BASE_URL}{img_path}"

            log(f"Found generated image URL: {img_url}")

            # Test GET on image URL
            r_img_get = requests.get(img_url, timeout=15)
            assert r_img_get.status_code == 200, f"GET image status: {r_img_get.status_code}"
            assert len(r_img_get.content) > 100, "Image binary content is empty"
            log(f"GET {img_path} returned HTTP 200 ({len(r_img_get.content)} bytes)")

            # Test HEAD on image URL
            r_img_head = requests.head(img_url, timeout=15)
            assert r_img_head.status_code == 200, f"HEAD image status: {r_img_head.status_code}"
            log(f"HEAD {img_path} returned HTTP 200")
        else:
            log("No comic page image URL found in response markdown", success=False)
            sys.exit(1)
    except Exception as e:
        log(f"POST /chat verification failed: {e}", success=False)
        sys.exit(1)

    # 5. Test missing file handling (HEAD & GET for non-existent image)
    try:
        missing_url = f"{BASE_URL}/static/cartoons/missing_test_image.jpg"
        r_head = requests.head(missing_url, timeout=10)
        assert r_head.status_code == 200, f"HEAD missing image status: {r_head.status_code}"
        log("HEAD missing_test_image.jpg returned HTTP 200 SVG fallback")

        r_get = requests.get(missing_url, timeout=10)
        assert r_get.status_code == 200, f"GET missing image status: {r_get.status_code}"
        assert "<svg" in r_get.text, "GET missing image did not return SVG fallback"
        log("GET missing_test_image.jpg returned HTTP 200 SVG fallback")
    except Exception as e:
        log(f"Missing image fallback test failed: {e}", success=False)
        sys.exit(1)

    print("\n==========================================")
    print("🎉 ALL LOCALHOST VERIFICATION CHECKS PASSED!")
    print("==========================================\n")

if __name__ == "__main__":
    test_endpoints()
