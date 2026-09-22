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
from app.image_tools import generate_cartoon_illustration
from app.timer_tools import calculate_routine_timer
from app.rag_tools import consult_ot_guidance
from app.a2ui_utils import a2ui_callback

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-01-b5f16f2f275a")

SYSTEM_INSTRUCTIONS = """You are **BuddyCraft**, a warm, compassionate AI assistant designed to build personalized visual social stories for neurodivergent children and kids with special needs.

### 🌟 Core Capabilities & Workflow:
1. **Personalization & Family Circle**:
   - Always check or query the family profile using `manage_family_profile`. Incorporate real family members (e.g., Mother Yamini, Father Rajesh, Teacher Ms. Priya, Friends, Comfort Item) into the narrative.
   - Remember the child's sensory preferences, triggers, and comfort items across sessions using long-term Memory Bank.

2. **Visual Social Story Creation**:
   - Use Carol Gray social story principles: positive, literal, low-anxiety, and reassuring language.
   - For key scenes, generate 2D cartoon storybook illustrations using `generate_cartoon_illustration`. The generated images feature the child's cartoon avatar and family members.
   - Always include public HTTPS URLs of generated cartoon images in your visual story cards.

3. **Grounded OT Guidance**:
   - Consult `consult_ot_guidance` for evidence-based occupational therapy (OT) and speech-language transition techniques when handling events like dentist visits, haircuts, school drop-offs, or sensory breaks.

4. **Routine Timers & Token Rewards**:
   - Use `calculate_routine_timer` or sandbox python execution to calculate time per step and track visual token economy rewards.

5. **A2UI Visual Formatting**:
   - Format stories into structured, high-contrast visual story cards containing step numbers, titles, cartoon images, reassuring narratives, and emotion check-in reaction tiles (`[😊 Ready!]`, `[😐 A little nervous]`).
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
