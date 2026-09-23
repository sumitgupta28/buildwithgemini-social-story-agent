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

from app.prompts import prompt_registry

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

SYSTEM_INSTRUCTIONS = prompt_registry.get_prompt("system_instructions")


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
