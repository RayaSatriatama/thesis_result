import os
import json
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file (if exists, for other settings)
load_dotenv()

# --- Google Cloud credentials (only needed when LLM_PROVIDER=google_vertexai) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credential.json")

PROJECT_ID: str | None = None

_google_provider = os.getenv("LLM_PROVIDER", "google_vertexai") == "google_vertexai"

if _google_provider:
    if not os.path.exists(CREDENTIALS_PATH):
        raise ValueError(
            f"credential.json not found at {CREDENTIALS_PATH}. "
            "This file is required when LLM_PROVIDER=google_vertexai. "
            "To use a different provider, set LLM_PROVIDER in your .env "
            "(e.g. LLM_PROVIDER=deepseek)."
        )
    try:
        with open(CREDENTIALS_PATH, "r") as f:
            creds = json.load(f)
            PROJECT_ID = creds.get("project_id")
            if not PROJECT_ID:
                raise ValueError("project_id not found in credential.json")
    except Exception as e:
        raise ValueError(f"Error reading credential.json: {str(e)}")
else:
    # Non-Google provider: credential.json is not required
    # Still try to read it for PROJECT_ID if it happens to exist
    if os.path.exists(CREDENTIALS_PATH):
        try:
            with open(CREDENTIALS_PATH, "r") as f:
                creds = json.load(f)
                PROJECT_ID = creds.get("project_id")
        except Exception:
            pass

# Model Configuration (backward-compat alias)
GEMINI_MODEL = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# LightRAG Configuration
_is_serverless = bool(
    os.getenv("VERCEL")
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    or os.getenv("LAMBDA_TASK_ROOT")
)

# On serverless (Vercel/Lambda), the project filesystem is read-only.
# Use the OS temp directory for any runtime scratch storage.
_serverless_tmp_lightrag = os.path.join(tempfile.gettempdir(), "lightrag_storage")
_default_working_dir = _serverless_tmp_lightrag if _is_serverless else "./data/lightrag_storage"
WORKING_DIR = os.getenv("LIGHTRAG_WORKING_DIR", _default_working_dir)

# Guard: even if LIGHTRAG_WORKING_DIR is set (e.g. from a local .env),
# keep serverless deployments on a writable path.
if _is_serverless and not WORKING_DIR.startswith(tempfile.gettempdir()):
    WORKING_DIR = _serverless_tmp_lightrag

if not os.path.exists(WORKING_DIR):
    try:
        os.makedirs(WORKING_DIR, exist_ok=True)
    except OSError:
        # If the path is not writable (e.g. misconfigured on serverless),
        # fallback to temp dir so the API can still boot without LightRAG.
        WORKING_DIR = _serverless_tmp_lightrag
        os.makedirs(WORKING_DIR, exist_ok=True)

# RAG Configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1200))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))
