import os
import vertexai
from vertexai.preview import rag

from app.app_utils.project_id import get_project_id

def _get_project_id() -> str:
    try:
        return get_project_id()
    except Exception:
        return ""

PROJECT_ID = _get_project_id()
RAG_CORPUS_RESOURCE = os.environ.get("RAG_CORPUS_RESOURCE", "")

try:
    vertexai.init(project=PROJECT_ID, location="us-central1")
except Exception:
    pass

# Grounded therapy knowledge base fallback
EVIDENCE_BASED_OT_GUIDELINES = {
    "dentist": (
        "Carol Gray Social Story Framework for Dental Visits:\n"
        "1. Describe the sensory environment (bright lights, gentle humming sounds).\n"
        "2. Reassure control: The child can raise a hand anytime to request a break.\n"
        "3. Emphasize positive reinforcement: Praise effort and reward with a comforting item."
    ),
    "school": (
        "School Transition Guidelines for ASD:\n"
        "1. Visual predictability: Show arrival, backpack storage, and greeting teacher.\n"
        "2. Provide explicit comforting anchors (e.g., Mom Yamini returns at 3:00 PM).\n"
        "3. Incorporate quiet corner break options if sensory overload occurs."
    ),
    "haircut": (
        "Haircut Sensory Strategies:\n"
        "1. Prepare for sound: Explain gentle clippers using low-frequency description.\n"
        "2. Tactile preparation: Use a soft cape or familiar t-shirt.\n"
        "3. Step-by-step token rewards for each completed minute."
    ),
}

def consult_ot_guidance(query: str) -> str:
    """Retrieves grounded evidence-based occupational therapy (OT) and speech guidance for social stories.

    Args:
        query: Therapeutic topic or transition (e.g., 'dentist visit', 'school arrival', 'sensory overload').

    Returns:
        Grounded transition strategies and Carol Gray social story guidelines.
    """
    if RAG_CORPUS_RESOURCE:
        try:
            response = rag.retrieval_query(
                rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_RESOURCE)],
                text=query,
                similarity_top_k=3,
            )
            contexts = []
            for ctx in getattr(response, "contexts", []):
                if hasattr(ctx, "text"):
                    contexts.append(ctx.text)
            if contexts:
                return "\n\n".join(contexts)
        except Exception:
            pass

    # Match topic keywords to evidence-based guidelines
    q_lower = query.lower()
    matched = []
    for key, val in EVIDENCE_BASED_OT_GUIDELINES.items():
        if key in q_lower:
            matched.append(val)

    if matched:
        return "\n\n".join(matched)

    return (
        "General Occupational Therapy Social Story Principles:\n"
        "- Use positive, reassuring, literal language (avoid metaphors).\n"
        "- Include descriptive, perspective, and affirmative statements.\n"
        "- Outline visual step countdowns and offer sensory break options."
    )
