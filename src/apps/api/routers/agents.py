"""
Agents Router - Individual agent endpoints
"""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

from ..schemas import (
    # Research
    ResearchPlanRequest, ResearchPlanResponse,
    ResearchQueryRequest, ResearchQueryResponse,
    ResearchSearchRequest,
    # Planner
    PlannerParseRequest, PlannerParseResponse,
    PlannerPlanRequest, PlannerPlanResponse,
    # Writer
    WriterDraftRequest, WriterDraftResponse,
    WriterReviseRequest,
    # Diagram
    DiagramPlanRequest, DiagramPlanResponse,
    DiagramRenderRequest, DiagramRenderResponse,
    # Critic
    CriticEvaluateRequest, CriticEvaluateResponse,
    # Image
    ImageGenerateRequest, ImageGenerateResponse,
)

# Import agents
try:
    from workflows.story_agent.agents import (
        ResearchAgent, PlannerAgent, WriterAgent,
        WriterDiagramAgent, CriticAgent, ImageGeneratorAgent
    )
    from workflows.story_agent.story_canvas import StoryCanvas
    from workflows.story_agent.integrations.langfuse_client import get_langfuse
    from workflows.story_agent.integrations.lightrag_client import LightRAGClient, get_lightrag_client
    from settings import LanguageConfig
    from config import CREDENTIALS_PATH, PROJECT_ID

    # Google credentials are only required for Vertex AI provider.
    credentials = None
    if (LanguageConfig is not None) and (  # defensive: keeps module import safe
        __import__("os").getenv("LLM_PROVIDER", "google_vertexai") == "google_vertexai"
    ):
        from google.oauth2 import service_account  # noqa: PLC0415

        credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)

    # Initialize LightRAG client for research endpoints using language config.
    # This is optional; endpoints handle missing client gracefully.
    lightrag_client = get_lightrag_client(LanguageConfig.SYSTEM_LANGUAGE)
    # Initialize Langfuse
    langfuse = get_langfuse()
    AGENTS_AVAILABLE = True
except Exception as e:
    logger.warning(f"[API::GALAT] Could not import agents: {e}")
    AGENTS_AVAILABLE = False
    credentials = None
    PROJECT_ID = None
    lightrag_client = None
    langfuse = None

router = APIRouter()


# =============================================================================
# Research Agent Endpoints
# =============================================================================

@router.post("/research/plan", response_model=ResearchPlanResponse)
async def research_plan(request: ResearchPlanRequest):
    """Create research plan for a theme"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    start = time.time()
    agent = ResearchAgent(credentials=credentials, project=PROJECT_ID)
    
    # Create plan
    agent = ResearchAgent(credentials=credentials, project=PROJECT_ID)
    
    # Trace execution
    if langfuse:
        with langfuse.trace_execution(
            name="ResearchPlan",
            metadata={"theme": request.theme, "target_age": request.target_age}
        ):
            plan = await agent._create_research_plan(
                theme=request.theme,
                target_age=request.target_age or "",
                language=request.language
            )
    else:
        # Fallback if Langfuse not available
        plan = await agent._create_research_plan(
            theme=request.theme,
            target_age=request.target_age or "",
            language=request.language
        )
    
    return ResearchPlanResponse(
        questions=[{"question": q.question, "tool": q.tool} for q in plan.questions],
        elapsed_time=round(time.time() - start, 2)
    )


@router.post("/research/query", response_model=ResearchQueryResponse)
async def research_query(request: ResearchQueryRequest):
    """Query knowledge graph using LightRAG"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    if not lightrag_client:
        return ResearchQueryResponse(
            content="LightRAG service not connected. Please ensure the LightRAG server is running.",
            sources=[],
            elapsed_time=0.0
        )
    
    start = time.time()
    try:
        # Direct LightRAG query
        result = await lightrag_client.query(request.query, mode="hybrid")
        content = result.response if result and result.response else ""
        sources = result.sources if result and hasattr(result, 'sources') else []
        
        return ResearchQueryResponse(
            content=content,
            sources=sources,
            elapsed_time=round(time.time() - start, 2)
        )
    except Exception as e:
        logger.warning(f"[RISET::PERINGATAN] LightRAG query failed: {e}")
        return ResearchQueryResponse(
            content=f"Query failed: {str(e)}",
            sources=[],
            elapsed_time=round(time.time() - start, 2)
        )


@router.post("/research/search", response_model=ResearchQueryResponse)
async def research_search(request: ResearchSearchRequest):
    """Web search"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    start = time.time()
    agent = ResearchAgent(credentials=credentials, project=PROJECT_ID)
    
    content = await agent._search_web(request.query)
    
    return ResearchQueryResponse(
        content=content,
        sources=[],
        elapsed_time=round(time.time() - start, 2)
    )


# =============================================================================
# Planner Agent Endpoints
# =============================================================================

@router.post("/planner/parse", response_model=PlannerParseResponse)
async def planner_parse(request: PlannerParseRequest):
    """Parse user request into story parameters using PlannerAgent"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    agent = PlannerAgent(credentials=credentials, project=PROJECT_ID)
    
    # Use PlannerAgent's unified plan with minimal state to extract parsed params
    from workflows.story_agent.state import StoryState
    minimal_state: StoryState = {
        "user_message": request.user_message,
        "language": "Indonesian",
        "story_length": "",
    }
    
    try:
        result = await agent.plan(minimal_state)
        return PlannerParseResponse(
            theme=result.get("theme", ""),
            target_age=result.get("target_age"),
            story_style=result.get("story_style"),
            narrative_style=result.get("narrative_style", "campuran"),
            emotional_tone=result.get("emotional_tone"),
            language=result.get("language", "Indonesian"),
            story_length=result.get("story_length", "")
        )
    except Exception as e:
        logger.error(f"Failed to parse request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/planner/plan", response_model=PlannerPlanResponse)
async def planner_plan(request: PlannerPlanRequest):
    """Generate story structure and plan"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    start = time.time()
    agent = PlannerAgent(credentials=credentials, project=PROJECT_ID)
    
    # Build state for planner
    state = {
        "theme": request.theme,
        "target_age": request.target_age or "",
        "research_notes": request.research_notes or "",
        "language": request.language,
        "story_length": request.story_length,
        "user_message": request.theme
    }
    
    if langfuse:
        with langfuse.trace_execution(
            name="PlannerPlan",
            metadata={"theme": request.theme}
        ):
            result = await agent.plan(state)
    else:
        result = await agent.plan(state)
    
    return PlannerPlanResponse(
        story_outline=result.get("story_outline", {}),
        characters=result.get("characters", []),
        moral_message=result.get("moral_message", ""),
        active_writers=result.get("active_writers", ["text"]),
        elapsed_time=round(time.time() - start, 2)
    )


# =============================================================================
# Writer Agent Endpoints
# =============================================================================

@router.post("/writer/draft", response_model=WriterDraftResponse)
async def writer_draft(request: WriterDraftRequest):
    """Generate first story draft"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    start = time.time()
    agent = WriterAgent(credentials=credentials, project=PROJECT_ID)
    
    state = {
        "theme": request.theme,
        "characters": request.characters,
        "story_outline": request.story_outline or {},
        "moral_message": request.moral_message or "",
        "target_age": request.target_age or "",
        "language": request.language,
        "story_length": request.story_length,
        "narrative_style": request.narrative_style,
        "revision_count": 0,
        "active_writers": ["text"]
    }
    
    if langfuse:
        with langfuse.trace_execution(
            name="WriterDraft",
            metadata={"theme": request.theme}
        ):
             result = await agent.write(state)
    else:
         result = await agent.write(state)
    draft = result.get("draft_content", "")
    
    return WriterDraftResponse(
        draft_content=draft,
        word_count=len(draft.split()),
        paragraph_count=len([p for p in draft.split("\n\n") if p.strip()]),
        elapsed_time=round(time.time() - start, 2)
    )


@router.post("/writer/revise", response_model=WriterDraftResponse)
async def writer_revise(request: WriterReviseRequest):
    """Revise story draft based on feedback"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    start = time.time()
    agent = WriterAgent(credentials=credentials, project=PROJECT_ID)
    
    state = {
        "draft_content": request.draft_content,
        "critique_feedback": request.critique_feedback,
        "revision_count": request.revision_count,
        "story_canvas": request.story_canvas,
        "structured_critique": request.structured_critique,
        "active_writers": ["text"],
        "needs_text_revision": True
    }
    
    if langfuse:
        with langfuse.trace_execution(name="WriterRevise"):
            result = await agent.write(state)
    else:
        result = await agent.write(state)
    draft = result.get("draft_content", "")
    
    return WriterDraftResponse(
        draft_content=draft,
        word_count=len(draft.split()),
        paragraph_count=len([p for p in draft.split("\n\n") if p.strip()]),
        elapsed_time=round(time.time() - start, 2)
    )


# =============================================================================
# Diagram Agent Endpoints
# =============================================================================

@router.post("/diagram/plan", response_model=DiagramPlanResponse)
async def diagram_plan(request: DiagramPlanRequest):
    """Generate diagram plan"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    try:
        agent = WriterDiagramAgent(credentials=credentials, project=PROJECT_ID)
        
        # Build state dict for the method (it expects StoryState dict)
        state = {
            "theme": request.theme,
            "story_outline": request.story_outline or {},
            "target_age": request.target_age or "",
            "research_notes": "",
            "characters": [],
            "moral_message": ""
        }
        
        # _generate_diagram_plan is SYNC, not async
        # _generate_diagram_plan is SYNC, not async
        if langfuse:
            with langfuse.trace_execution(name="DiagramPlan"):
                 plan = agent._generate_diagram_plan(state)
        else:
             plan = agent._generate_diagram_plan(state)
        
        return DiagramPlanResponse(
            diagram_type=plan.diagram_type if plan else "",
            title=plan.title if plan else "",
            mermaid_code=plan.mermaid_code if plan else ""
        )
    except Exception as e:
        logger.error(f"[DIAGRAM::GALAT] Plan generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagram/render", response_model=DiagramRenderResponse)
async def diagram_render(request: DiagramRenderRequest):
    """Render Mermaid diagram to PNG"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    try:
        import uuid
        agent = WriterDiagramAgent(credentials=credentials, project=PROJECT_ID)
        
        # session_id is the second parameter, not filename
        session_id = request.output_filename or f"api_{uuid.uuid4().hex[:8]}"
        png_path = agent._render_mermaid_to_png(
            mermaid_code=request.mermaid_code,
            session_id=session_id
        )
        
        # Calculate mmd_path from session_id
        import os
        timestamp = int(time.time())
        mmd_path = os.path.join(agent.output_dir, f"diagram_{session_id}_{timestamp}.mmd")
        
        return DiagramRenderResponse(
            mmd_path=mmd_path if os.path.exists(mmd_path) else None,
            png_path=png_path,
            success=png_path is not None
        )
    except Exception as e:
        logger.error(f"[DIAGRAM::GALAT] Render failed: {e}")
        return DiagramRenderResponse(
            mmd_path=None,
            png_path=None,
            success=False
        )


# =============================================================================
# Critic Agent Endpoints
# =============================================================================

@router.post("/critic/evaluate", response_model=CriticEvaluateResponse)
async def critic_evaluate(request: CriticEvaluateRequest):
    """Full evaluation of story draft"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    agent = CriticAgent(credentials=credentials, project=PROJECT_ID)
    
    state = {
        "draft_content": request.draft_content,
        "theme": request.theme,
        "target_age": request.target_age or "",
        "characters": request.characters,
        "moral_message": request.moral_message or "",
        "revision_count": request.revision_count
    }
    
    if langfuse:
        with langfuse.trace_execution(name="CriticEvaluate"):
            result = await agent.critique(state)
    else:
        result = await agent.critique(state)
    
    return CriticEvaluateResponse(
        quality_score=result.get("quality_score", 0),
        educational_score=result.get("educational_score", 0),
        coherence_score=result.get("coherence_score", 0),
        feedback=result.get("critique_feedback", ""),
        decision=result.get("critique_decision", "REVISE"),
        coherence_issues=result.get("coherence_issues", [])
    )


# =============================================================================
# Image Agent Endpoints
# =============================================================================

@router.post("/image/generate", response_model=ImageGenerateResponse)
async def image_generate(request: ImageGenerateRequest):
    """Generate illustration"""
    if not AGENTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agents not available")
    
    start = time.time()
    try:
        import uuid
        agent = ImageGeneratorAgent(credentials=credentials, project=PROJECT_ID)
        
        # _generate_single_image is SYNC, not async
        # _generate_single_image is SYNC, not async
        # It expects: prompt, scene_index, session_id
        session_id = request.output_filename or f"api_{uuid.uuid4().hex[:8]}"
        
        if langfuse:
            with langfuse.trace_execution(name="ImageGenerate", session_id=session_id):
                result = agent._generate_single_image(
                    prompt=request.prompt,
                    scene_index=0,
                    session_id=session_id
                )
        else:
            result = agent._generate_single_image(
                prompt=request.prompt,
                scene_index=0,
                session_id=session_id
            )
        
        # result is GeneratedImage pydantic model
        return ImageGenerateResponse(
            success=result.success,
            file_path=result.file_path,
            error=result.error_message,
            elapsed_time=round(time.time() - start, 2)
        )
    except Exception as e:
        logger.error(f"[GAMBAR::GALAT] Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
