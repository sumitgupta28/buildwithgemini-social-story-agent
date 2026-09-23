import os
import datetime

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

from app.app_utils.project_id import get_project_id

def _get_project_id() -> str:
    try:
        return get_project_id()
    except Exception:
        return ""

PROJECT_ID = _get_project_id()

_MEMORY_FAMILY_PROFILES = {}
_MEMORY_STORIES = []

_ACTIVE_PROFILE = {
    "child_name": "Aarav",
    "mother_name": "Yamini",
    "father_name": "Rajesh",
    "avatar_url": "",
    "characters": [
        {"name": "Ms. Priya", "role": "Teacher"},
        {"name": "Dr. Smith", "role": "Dentist"},
        {"name": "Mr. Marco", "role": "Barber"},
        {"name": "Dr. Sam", "role": "Doctor"},
    ]
}

def get_active_profile() -> dict:
    """Returns a copy of the active kid's profile."""
    return dict(_ACTIVE_PROFILE)

def update_active_profile(data: dict) -> dict:
    """Updates the active kid's profile."""
    global _ACTIVE_PROFILE
    if "child_name" in data and data["child_name"]:
        _ACTIVE_PROFILE["child_name"] = str(data["child_name"]).strip()
    if "mother_name" in data and data["mother_name"]:
        _ACTIVE_PROFILE["mother_name"] = str(data["mother_name"]).strip()
    if "father_name" in data and data["father_name"]:
        _ACTIVE_PROFILE["father_name"] = str(data["father_name"]).strip()
    if "avatar_url" in data:
        _ACTIVE_PROFILE["avatar_url"] = str(data["avatar_url"]).strip()
    if "characters" in data and isinstance(data["characters"], list):
        _ACTIVE_PROFILE["characters"] = data["characters"]
    return dict(_ACTIVE_PROFILE)

def ensure_character_in_profile(role: str, default_name: str) -> str:
    """Ensures a character with the given role exists in the profile; adds it if missing."""
    global _ACTIVE_PROFILE
    role_clean = role.strip().lower()
    for char in _ACTIVE_PROFILE.get("characters", []):
        if char.get("role", "").strip().lower() == role_clean or char.get("name", "").strip().lower() == default_name.strip().lower():
            return char.get("name")
    
    # Add new character
    new_char = {"name": default_name.strip(), "role": role.strip()}
    _ACTIVE_PROFILE.setdefault("characters", []).append(new_char)
    return default_name.strip()


def get_firestore_client():
    if firestore is None:
        return None
    try:
        return firestore.Client(project=PROJECT_ID)
    except Exception:
        return None

def manage_family_profile(
    child_name: str,
    action: str = "get",
    mother_name: str = None,
    father_name: str = None,
    teacher_name: str = None,
    friends: list[str] = None,
    comfort_item: str = None,
) -> str:
    """Manages the child's family profile and key support characters in Firestore.

    Args:
        child_name: Name of the child (e.g., 'Aarav').
        action: Either 'get' to retrieve the profile or 'set' to update it.
        mother_name: Mother's name (e.g., 'Yamini').
        father_name: Father's name (e.g., 'Rajesh').
        teacher_name: Teacher's name (e.g., 'Ms. Priya').
        friends: List of close friend names.
        comfort_item: Favorite comforting item (e.g., 'Blue teddy bear').

    Returns:
        JSON string or status message with the family profile details.
    """
    c_key = child_name.strip().lower()

    if action.lower() == "set":
        data = {
            "child_name": child_name.strip(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if mother_name:
            data["mother_name"] = mother_name.strip()
        if father_name:
            data["father_name"] = father_name.strip()
        if teacher_name:
            data["teacher_name"] = teacher_name.strip()
        if friends is not None:
            data["friends"] = friends
        if comfort_item:
            data["comfort_item"] = comfort_item.strip()

        try:
            db = get_firestore_client()
            if db:
                doc_ref = db.collection("family_profiles").document(c_key)
                doc_ref.set(data, merge=True)
        except Exception as e:
            print(f"Firestore set profile warning: {e}")

        if c_key not in _MEMORY_FAMILY_PROFILES:
            _MEMORY_FAMILY_PROFILES[c_key] = {}
        _MEMORY_FAMILY_PROFILES[c_key].update(data)
        return f"Successfully updated family profile for {child_name}."

    else:
        # Action: get
        profile = None
        try:
            db = get_firestore_client()
            if db:
                doc_ref = db.collection("family_profiles").document(c_key)
                doc = doc_ref.get()
                if doc.exists:
                    profile = doc.to_dict()
        except Exception as e:
            print(f"Firestore get profile warning: {e}")

        if not profile:
            profile = _MEMORY_FAMILY_PROFILES.get(c_key)

        if not profile:
            return f"No family profile found for '{child_name}'. You can set one using action='set'."
        
        details = [f"Profile for {profile.get('child_name', child_name)}:"]
        if "mother_name" in profile:
            details.append(f"- Mother: {profile['mother_name']}")
        if "father_name" in profile:
            details.append(f"- Father: {profile['father_name']}")
        if "teacher_name" in profile:
            details.append(f"- Teacher: {profile['teacher_name']}")
        if "friends" in profile and profile["friends"]:
            details.append(f"- Friends: {', '.join(profile['friends'])}")
        if "comfort_item" in profile:
            details.append(f"- Comfort Item: {profile['comfort_item']}")
        
        return "\n".join(details)


def save_social_story(child_name: str, story_title: str, steps: list[str]) -> str:
    """Saves a generated social story to Firestore for future replay.

    Args:
        child_name: Name of the child the story was created for.
        story_title: Title of the story (e.g., 'Aarav Goes to the Dentist').
        steps: List of text step descriptions included in the story.

    Returns:
        Status message confirming the story was saved.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    doc_id = f"{child_name.strip().lower()}_{now.strftime('%Y%m%d_%H%M%S')}"

    story_data = {
        "child_name": child_name.strip(),
        "story_title": story_title.strip(),
        "steps": steps,
        "created_at": now.isoformat(),
    }

    try:
        db = get_firestore_client()
        if db:
            db.collection("social_stories").document(doc_id).set(story_data)
    except Exception as e:
        print(f"Firestore save story warning: {e}")

    _MEMORY_STORIES.append(story_data)
    return f"Saved social story '{story_title}' for {child_name} with ID {doc_id}."

