import pytest
from fastapi.testclient import TestClient
from frontend.main import app

client = TestClient(app)

def test_suggest_storyline_api():
    response = client.post("/api/suggest_storyline", json={
        "topic": "Taking Bath",
        "category": "routines",
        "comfort": "Rubber Duckie"
    })
    assert response.status_code == 200
    data = response.json()
    assert "description" in data
    assert len(data["description"]) > 10

def test_add_scenario_title_clean():
    response = client.post("/api/scenarios", json={
        "title": "Taking Bath",
        "category": "routines",
        "description": "Step 1: Preparing | Mom: Time for bath! | Child: Ready!",
        "prompt": "Taking Bath",
        "icon": "🛁"
    })
    assert response.status_code == 200
    data = response.json()
    # Scenario title must NOT contain kid's name
    assert data["title"] == "Taking Bath"
    assert "Vardaan" not in data["title"]
    assert "Aarav" not in data["title"]
