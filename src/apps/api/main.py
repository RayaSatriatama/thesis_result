"""
FastAPI Main Application for Story Agent
"""

import sys
from pathlib import Path

# Configure Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from apps.api.routers import workflow, agents, interactive, meta
from apps.api.schemas import HealthResponse
from apps.api.dependencies.auth import verify_api_key

# Initialize language configuration from environment variables immediately
# This ensures it works when running via uvicorn
from settings import LanguageConfig, StoryConfig
from workflows.story_agent.prompts import init_registry

init_registry(LanguageConfig.SYSTEM_LANGUAGE)
logger.info(f"[API::KONFIGURASI] System language initialized: {LanguageConfig.SYSTEM_LANGUAGE} ({LanguageConfig.get_display_name()})")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — eagerly build both workflow singletons so the first real request
    # does not pay the 10–15 s agent-initialisation cost.
    logger.info("[API::MEMULAI] Story Agent API starting...")
    # Serverless platforms (Vercel/Lambda) have strict cold-start constraints.
    # Pre-warming can exceed the startup budget and crash the function.
    is_serverless = bool(
        os.getenv("VERCEL")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("LAMBDA_TASK_ROOT")
    )
    if is_serverless:
        logger.info("[API::WARMUP] Skipped (serverless runtime detected).")
    else:
        import asyncio
        try:
            logger.info("[API::WARMUP] Pre-warming workflow instances...")
            await asyncio.gather(
                asyncio.to_thread(workflow._get_workflow),
                asyncio.to_thread(interactive._get_workflow),
            )
            logger.success("[API::WARMUP] Workflow instances ready.")
        except Exception as exc:
            logger.warning(f"[API::WARMUP] Pre-warm failed (will retry on first request): {exc}")
    yield
    # Shutdown
    logger.info("[API::SELESAI] Story Agent API shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Story Agent API",
    description="REST API for Story-Based Learning AI with Agentic Workflow",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware - restrict to allowed origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
allowed_origins = [origin.strip() for origin in allowed_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (protected with API key)
app.include_router(
    workflow.router,
    prefix="/api/workflow",
    tags=["Workflow"],
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    agents.router,
    prefix="/api/agents",
    tags=["Agents"],
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    interactive.router,
    prefix="/api/interactive",
    tags=["Interactive"],
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    meta.router,
    prefix="/api/meta",
    tags=["Meta"],
    dependencies=[Depends(verify_api_key)],
)

# Conditional fake-log replay router (no auth — dev tool only)
if os.getenv("ENABLE_FAKE_LOGS", "").lower() == "true":
    from apps.api.routers import fake_logs
    app.include_router(fake_logs.router, prefix="/api/fake", tags=["fake-logs"])
    logger.info("[API::FAKE] Fake-log router mounted at /api/fake")

# Serve static files (test UI, etc.) from the public/ directory
_public_dir = PROJECT_ROOT / "public"
if _public_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")
    logger.info(f"[API::STATIC] Serving static files from {_public_dir}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        agents_available=10
    )




if __name__ == "__main__":
    import uvicorn
    import argparse
    from settings import StoryConfig, LanguageConfig
    from workflows.story_agent.prompts import init_registry
    
    parser = argparse.ArgumentParser(description="Story Agent API")
    parser.add_argument("--image", action="store_true", help="Enable Image Writer")
    parser.add_argument("--diagram", action="store_true", help="Enable Diagram Writer")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on")
    parser.add_argument("--lang", type=str, default="id", choices=["id", "en"], help="System language (id/en)")
    
    args = parser.parse_args()
    
    # CLI arguments override environment variables
    if args.lang:
        LanguageConfig.set_language(args.lang)
        init_registry(args.lang)
        logger.info(f"[API::KONFIGURASI] System language overridden via CLI: {args.lang} ({LanguageConfig.get_display_name()})")
        
    if args.image:
        StoryConfig.ENABLE_IMAGE_WRITER = True
        logger.info("[API::KONFIGURASI] Image Writer ENABLED via CLI flag")
        
    if args.diagram:
        StoryConfig.ENABLE_DIAGRAM_WRITER = True
        logger.info("[API::KONFIGURASI] Diagram Writer ENABLED via CLI flag")
        
    uvicorn.run(app, host=args.host, port=args.port)
