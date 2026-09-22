import os
import datetime

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-01-b5f16f2f275a")
_MEMORY_FAMILY_PROFILES = {}
_MEMORY_STORIES = []

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
    try:
        db = get_firestore_client()
        doc_ref = db.collection("family_profiles").document(child_name.strip().lower())

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

            doc_ref.set(data, merge=True)
            return f"Successfully updated family profile for {child_name}."

        else:
            # Action: get
            doc = doc_ref.get()
            if not doc.exists:
                return f"No family profile found for '{child_name}'. You can set one using action='set'."
            
            profile = doc.to_dict()
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

    except Exception as e:
        return f"Error accessing Firestore family profile: {str(e)}"


def save_social_story(child_name: str, story_title: str, steps: list[str]) -> str:
    """Saves a generated social story to Firestore for future replay.

    Args:
        child_name: Name of the child the story was created for.
        story_title: Title of the story (e.g., 'Aarav Goes to the Dentist').
        steps: List of text step descriptions included in the story.

    Returns:
        Status message confirming the story was saved.
    """
    try:
        db = get_firestore_client()
        now = datetime.datetime.now(datetime.timezone.utc)
        doc_id = f"{child_name.strip().lower()}_{now.strftime('%Y%m%d_%H%M%S')}"

        story_data = {
            "child_name": child_name.strip(),
            "story_title": story_title.strip(),
            "steps": steps,
            "created_at": now.isoformat(),
        }

        db.collection("social_stories").document(doc_id).set(story_data)
        return f"Saved social story '{story_title}' for {child_name} with ID {doc_id}."

    except Exception as e:
        return f"Error saving social story: {str(e)}"
