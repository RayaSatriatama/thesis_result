"""
Pydantic schemas for Story Agent FastAPI
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from enum import Enum

# =============================================================================
# Request Schemas
# =============================================================================

class WorkflowRequest(BaseModel):
    """Request for full story workflow"""
    prompt: str = Field(..., description="User prompt for story generation")
    target_age: Optional[str] = Field(None, description="Target age group")
    language: str = Field("Indonesian", description="Output language")
    story_length: Optional[str] = Field(None, description="Story length")
    active_writers: Optional[List[str]] = Field(
        None, 
        description="Writers to activate: text, diagram, image. If None, planner decides."
    )
    model: Optional[str] = Field(
        None,
        description="Override LLM model name (e.g. 'gemma4:e4b' for Ollama). If None, uses env default."
    )

class ResearchPlanRequest(BaseModel):
    """Request for research planning"""
    theme: str = Field(..., description="Story theme to research")
    target_age: Optional[str] = Field(None)
    language: str = Field("Indonesian")

class ResearchQueryRequest(BaseModel):
    """Request for knowledge graph query"""
    query: str = Field(..., description="Query for knowledge graph")
    mode: str = Field("hybrid", description="Query mode: local, global, hybrid, naive, mix")

class ResearchSearchRequest(BaseModel):
    """Request for web search"""
    query: str = Field(..., description="Web search query")

class PlannerParseRequest(BaseModel):
    """Request for parsing user request"""
    user_message: str = Field(..., description="Raw user message to parse")

class PlannerPlanRequest(BaseModel):
    """Request for story planning"""
    theme: str = Field(..., description="Story theme")
    target_age: Optional[str] = Field(None)
    research_notes: Optional[str] = Field(None, description="Research notes from researcher")
    language: str = Field("Indonesian")
    story_length: str = Field("medium")

class WriterDraftRequest(BaseModel):
    """Request for writing first draft"""
    theme: str = Field(..., description="Story theme")
    characters: List[dict] = Field(default_factory=list)
    story_outline: Optional[dict] = Field(None)
    moral_message: Optional[str] = Field(None)
    target_age: Optional[str] = Field(None)
    language: str = Field("Indonesian")
    story_length: str = Field("medium")
    narrative_style: str = Field("campuran")

class WriterReviseRequest(BaseModel):
    """Request for revising story"""
    draft_content: str = Field(..., description="Current story draft")
    critique_feedback: str = Field(..., description="Feedback from critic")
    revision_count: int = Field(1)
    story_canvas: Optional[dict] = Field(None)
    structured_critique: Optional[dict] = Field(None)

class DiagramPlanRequest(BaseModel):
    """Request for diagram planning"""
    theme: str = Field(..., description="Story theme for diagram")
    story_outline: Optional[dict] = Field(None)
    target_age: Optional[str] = Field(None)

class DiagramRenderRequest(BaseModel):
    """Request for rendering Mermaid diagram"""
    mermaid_code: str = Field(..., description="Mermaid diagram code")
    output_filename: Optional[str] = Field(None)

class CriticEvaluateRequest(BaseModel):
    """Request for full evaluation"""
    draft_content: str = Field(..., description="Story draft")
    theme: str = Field(..., description="Story theme")
    target_age: Optional[str] = Field(None)
    characters: List[dict] = Field(default_factory=list)
    moral_message: Optional[str] = Field(None)
    revision_count: int = Field(0)

class ImageGenerateRequest(BaseModel):
    """Request for image generation"""
    prompt: str = Field(..., description="Image generation prompt")
    style: Optional[str] = Field(None, description="Image style")
    output_filename: Optional[str] = Field(None)

class PriorStoryPayload(BaseModel):
    """One completed story from the UI session (for supervisor recall, not full checkpoint)."""
    title: str = Field("", max_length=500)
    excerpt: str = Field("", max_length=8000)


class InteractiveRequest(BaseModel):
    """Request for interactive story chat"""
    thread_id: str = Field(..., description="Unique thread identifier")
    user_message: str = Field(..., description="User message or prompt")
    language: str = Field("Indonesian", description="Story language")
    target_age: Optional[str] = Field(None, description="Target age group")
    story_length: Optional[str] = Field(None, description="Desired story length")
    active_writers: Optional[List[str]] = Field(None, description="Specific writers to activate")
    hitl_resume: Optional[str] = Field(None, description="Human feedback to resume paused workflow")
    model: Optional[str] = Field(None, description="Override LLM model name")
    history: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Recent UI chat turns (e.g. role=user|ai, text=...) for supervisor context; no DB required",
    )
    prior_stories: Optional[List[PriorStoryPayload]] = Field(
        None,
        description="Earlier completed stories in this UI session (title + excerpt); supervisor can reference or continue them",
    )

class SupervisorRouteRequest(BaseModel):
    """Request for standalone supervisor routing"""
    user_message: str = Field(..., description="User message or prompt")
    language: str = Field("Indonesian", description="Story language")
    draft_content: Optional[str] = Field(None, description="Current draft content")
    final_story: Optional[str] = Field(None, description="Completed story content")
    characters: Optional[List[dict]] = Field(None, description="Extracted characters")
    moral_message: Optional[str] = Field(None, description="Story moral message")
    hitl_feedback: Optional[str] = Field(None, description="Human feedback from previous turn")

class DirectorScriptRequest(BaseModel):
    """Request for standalone director script generation"""
    story_content: str = Field(..., description="Final story text to convert to script")
    language: str = Field("Indonesian", description="Story language")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    characters: Optional[List[dict]] = Field(None, description="Story characters")
    moral_message: Optional[str] = Field(None, description="Story moral message")
    theme: Optional[str] = Field(None, description="Story theme")

# =============================================================================
# Response Schemas
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "ok"
    version: str = "1.0.0"
    agents_available: int = 8

class WorkflowStatusResponse(BaseModel):
    """Workflow status response"""
    job_id: str
    status: str
    stream_url: Optional[str] = None

class ResearchPlanResponse(BaseModel):
    """Research plan response"""
    questions: List[dict]
    elapsed_time: float

class ResearchQueryResponse(BaseModel):
    """Knowledge graph query response"""
    content: str
    sources: List[str] = Field(default_factory=list)
    elapsed_time: float

class PlannerParseResponse(BaseModel):
    """Parsed request response"""
    theme: str
    target_age: Optional[str]
    story_style: Optional[str]
    narrative_style: str
    emotional_tone: Optional[str]
    language: str
    story_length: str

class PlannerPlanResponse(BaseModel):
    """Story plan response"""
    story_outline: dict
    characters: List[dict]
    moral_message: str
    active_writers: List[str]
    elapsed_time: float

class WriterDraftResponse(BaseModel):
    """Writer draft response"""
    draft_content: str
    word_count: int
    paragraph_count: int
    elapsed_time: float

class DiagramPlanResponse(BaseModel):
    """Diagram plan response"""
    diagram_type: str
    title: str
    mermaid_code: str

class DiagramRenderResponse(BaseModel):
    """Diagram render response"""
    mmd_path: str
    png_path: Optional[str] = None
    success: bool

class CriticEvaluateResponse(BaseModel):
    """Full evaluation response"""
    quality_score: float
    educational_score: float
    coherence_score: float
    feedback: str
    decision: str  # APPROVE or REVISE
    coherence_issues: List[Any] = Field(default_factory=list)

class ImageGenerateResponse(BaseModel):
    """Image generation response"""
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    elapsed_time: float

class SupervisorRouteResponse(BaseModel):
    """Response from standalone supervisor routing"""
    next_step: str
    interaction_mode: str
    reasoning: str
    direct_response: Optional[str] = None
    modification_scope: Optional[str] = None
    elapsed_time: float

class DirectorScriptResponse(BaseModel):
    """Response from standalone director script generation"""
    script_content: str
    script_file_path: str
    scene_count: int
    elapsed_time: float

class SSEEvent(BaseModel):
    """SSE event format"""
    event: str  # e.g., "RISET::MULAI"
    data: dict
