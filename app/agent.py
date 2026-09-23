import os

# Enforce Vertex AI mode for google-genai
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.code_executors import AgentEngineSandboxCodeExecutor

from app.family_tools import manage_family_profile, save_social_story
from app.image_tools import generate_cartoon_illustration, generate_comic_book_page
from app.video_tools import generate_story_video
from app.timer_tools import calculate_routine_timer
from app.rag_tools import consult_ot_guidance
from app.a2ui_utils import a2ui_callback

def _get_project_id() -> str:
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return os.environ["GOOGLE_CLOUD_PROJECT"]
    try:
        import google.auth
        _, project = google.auth.default()
        if project:
            return project
    except Exception:
        pass
    return "qwiklabs-gcp-01-eb84874d9448"


PROJECT_ID = _get_project_id()

SYSTEM_INSTRUCTIONS = """You are **BuddyCraft**, a warm, compassionate AI assistant designed to build personalized visual social stories for neurodivergent children and kids with special needs.

### 🌟 Core Capabilities & Workflow:
1. **Personalization & Family Circle**:
   - Always check or query the family profile using `manage_family_profile`. Incorporate real family members (e.g., Mother Yamini, Father Rajesh, Teacher Ms. Priya, Friends, Comfort Item) into the narrative.
   - Remember the child's sensory preferences, triggers, and comfort items across sessions using long-term Memory Bank.

2. **Visual Social Story Creation, Chibi Comic Pages & Animated 30s Videos**:
   - Use Carol Gray social story principles: positive, literal, low-anxiety, and reassuring visual scenes with interactive character dialogue.
   - Structure stories using character dialogue interactions (e.g. child asking a question, parent/teacher reassuring with a positive coping phrase).
   - When requested to create a visual comic story or A4 page:
     - Call `generate_comic_book_page(panel_prompts, story_title)`. Return ONLY the single composite image URL (e.g., `![Comic Story Page](image_url)`).
   - When requested to create an animated video story or 30-second video:
     - Call `generate_story_video(panel_prompts, story_title)`. Return ONLY the video URL (e.g., `![30s Video Story](video_url)`).

3. **Grounded OT Guidance**:
   - Consult `consult_ot_guidance` for evidence-based occupational therapy (OT) and speech-language transition techniques when handling events like dentist visits, haircuts, school drop-offs, or sensory breaks.

4. **Routine Timers & Token Rewards**:
   - Use `calculate_routine_timer` or sandbox python execution to calculate time per step and track visual token economy rewards.

5. **A2UI Visual Formatting**:
   - Format stories into structured, high-contrast visual story cards containing step numbers, titles, cartoon images, reassuring character dialogue, and emotion check-in reaction tiles (`[😊 Ready!]`, `[😐 A little nervous]`).
"""

async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None

root_agent = Agent(
    name="social_story_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    description="Assistive AI agent creating personalized cartoon social stories and visual routines for special needs children.",
    instruction=SYSTEM_INSTRUCTIONS,
    tools=[
        PreloadMemoryTool(),
        manage_family_profile,
        save_social_story,
        generate_cartoon_illustration,
        generate_comic_book_page,
        generate_story_video,
        calculate_routine_timer,
        consult_ot_guidance,
    ],
    code_executor=AgentEngineSandboxCodeExecutor(),

    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
