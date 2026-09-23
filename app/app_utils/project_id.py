import os
import subprocess
from typing import Optional


def get_project_id() -> str:
    """Resolves the current Google Cloud Project ID cleanly without hardcoded fallbacks.

    Resolution Priority:
    1. Environment variable: GOOGLE_CLOUD_PROJECT
    2. Environment variable: PROJECT_ID
    3. Google Auth default application credentials metadata
    4. gcloud CLI current project configuration

    Raises:
        RuntimeError: If the project ID cannot be resolved through any source.
    """
    # 1. Environment variables
    if project_id := os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return project_id
    if project_id := os.environ.get("PROJECT_ID"):
        return project_id

    # 2. Google Auth Application Default Credentials
    try:
        import google.auth
        _, auth_project = google.auth.default()
        if auth_project:
            return auth_project
    except Exception:
        pass

    # 3. gcloud CLI fallback
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            project_id = res.stdout.strip()
            if project_id != "(unset)":
                return project_id
    except Exception:
        pass

    raise RuntimeError(
        "Could not resolve Google Cloud Project ID. Please set GOOGLE_CLOUD_PROJECT "
        "or PROJECT_ID environment variable, or log in via `gcloud auth application-default login`."
    )
