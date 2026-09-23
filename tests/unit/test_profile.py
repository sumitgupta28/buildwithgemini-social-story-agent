import pytest
from app.family_tools import (
    get_active_profile,
    update_active_profile,
    ensure_character_in_profile
)

def test_get_active_profile_default():
    profile = get_active_profile()
    assert "child_name" in profile
    assert "mother_name" in profile
    assert "characters" in profile
    assert isinstance(profile["characters"], list)

def test_update_active_profile():
    new_data = {
        "child_name": "Leo",
        "mother_name": "Elena",
        "father_name": "David",
        "characters": [{"name": "Dr. Watson", "role": "Dentist"}]
    }
    updated = update_active_profile(new_data)
    assert updated["child_name"] == "Leo"
    assert updated["mother_name"] == "Elena"
    assert updated["father_name"] == "David"
    assert len(updated["characters"]) == 1
    assert updated["characters"][0]["name"] == "Dr. Watson"

def test_ensure_character_in_profile_auto_adds():
    # Reset active profile for testing
    update_active_profile({
        "child_name": "Leo",
        "mother_name": "Elena",
        "characters": []
    })
    
    # Dentist should be auto-added with default name
    name = ensure_character_in_profile("Dentist", "Dr. Smith")
    assert name == "Dr. Smith"
    
    profile = get_active_profile()
    assert len(profile["characters"]) == 1
    assert profile["characters"][0]["role"] == "Dentist"
    assert profile["characters"][0]["name"] == "Dr. Smith"
    
    # Second call for Dentist should return existing name without duplicating
    name2 = ensure_character_in_profile("Dentist", "Dr. Smith")
    assert name2 == "Dr. Smith"
    profile2 = get_active_profile()
    assert len(profile2["characters"]) == 1
