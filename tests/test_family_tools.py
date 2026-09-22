import pytest
from app.family_tools import manage_family_profile, save_social_story

def test_manage_family_profile_set_and_get():
    # Set profile
    res_set = manage_family_profile(
        child_name="Aarav",
        action="set",
        mother_name="Yamini",
        father_name="Rajesh",
        teacher_name="Ms. Priya",
        comfort_item="Blue teddy bear",
    )
    assert "Successfully updated" in res_set or "Error" not in res_set

    # Get profile
    res_get = manage_family_profile(child_name="Aarav", action="get")
    assert "Aarav" in res_get
    assert "Yamini" in res_get
    assert "Ms. Priya" in res_get

def test_save_social_story():
    res = save_social_story(
        child_name="Aarav",
        story_title="Aarav Visits the Dentist",
        steps=["Step 1: Get in the car with Mom Yamini", "Step 2: Sit in the dentist chair"],
    )
    assert "Saved social story" in res
