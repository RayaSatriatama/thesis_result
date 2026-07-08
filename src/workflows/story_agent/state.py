"""
State schema for Story-Based Learning Agent
Defines the global state tracked across the workflow
"""

from typing import TypedDict, List, Dict, Annotated, Any

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired
import operator


class StoryState(TypedDict):
    """
    Global state for story generation workflow.
    Tracks all 8 stages of the story-based learning process.
    """
    
    # User Inputs (Stage 1)
    user_message: str  # Raw user request message (for planner parsing)
    _parsed: bool  # Flag to indicate if user_message has been parsed
    learning_objectives: str  # Educational goals (optional)
    target_age: str  # Age range: "5-7", "8-10", "11-13", "14-17", "18+" (optional)
    theme: str  # Story theme/topic
    
    # User-specified story elements (must be respected by agents)
    user_characters: str  # User-specified character names and descriptions
    user_setting: str  # User-specified story setting/location
    
    # Enriched Context from Parser (for Planner)
    story_style: str  # Story style/genre (adventure, fable, mystery, etc.)
    narrative_style: str  # Narrative style: campuran, dialog_dominan, monolog_dominan, etc.
    emotional_tone: str  # Emotional tone (heartwarming, exciting, etc.)
    enriched_context: str  # Combined creative suggestions for planner
    
    # Language and Length Settings
    language: str  # Output language (default: "Indonesian")
    story_length: str  # Length: "short", "medium", "long" (default: "medium")
    
    # Workflow Tracking
    current_stage: str  # "research", "planning", "writing", "critique", "finalize"
    messages: Annotated[List[Dict], operator.add]  # Agent conversation history
    
    # Stage 2: Research & Ideas
    research_notes: str  # Educational content gathered
    research_sources: List[Dict]  # List of sources found (title, uri)
    used_sources: List[str]      # List of URIs explicitly selected by writer
    retrieved_contexts: List[str] # Raw research chunks for Ragas evaluation
    web_research_details: List[Dict] # Per-question web results: {question, answer, source_uris}
    
    # Stage 3-4: Outline & Characters
    story_outline: Dict  # Narrative structure
    characters: List[Dict]  # Character profiles
    moral_message: str  # The lesson to convey
    
    # Stage 5: Writing
    draft_title: str  # The title of the story
    draft_content: str  # Current story draft
    
    # Stage 8: Evaluation (Reflexion Loop)
    critique_feedback: str  # Editor's feedback
    revision_count: int  # Safety counter for loops
    quality_score: float  # 0-10 rating
    
    # Canvas-based revision system
    story_canvas: Dict  # Serialized StoryCanvas for paragraph-level editing
    structured_critique: Dict  # Serialized StructuredCritique from critic
    coherence_issues: List[str]  # List of coherence issues found
    
    # Revision History Tracking (for diff analysis) - kept for backward compatibility
    revision_history: List[Dict]  # List of {version, content, feedback_received}
    
    # Final Output
    final_story: str  # Approved story
    
    # Generated Images (from ImageGeneratorAgent)
    generated_images: List[Dict]  # List of generated illustration metadata
    
    # Planner Decision (which writers to activate)
    active_writers: List[str]  # e.g., ["text", "image"] or ["text", "diagram", "image"]
    
    # Diagram Writer Output
    draft_diagram: str  # Mermaid code for educational diagram
    diagram_image_path: str  # Path to generated PNG from MCP
    diagram_title: str  # Title of the diagram
    
    # Per-Writer Revision Flags (set by Critic)
    needs_text_revision: bool
    needs_image_revision: bool
    needs_diagram_revision: bool
    
    # Metadata
    session_id: str  # For Langfuse tracking
    trace_id: str    # For Langfuse trace linking
    total_tokens: int  # Token usage

    # --- Supervisor / Interactive Router Fields ---
    supervisor_next: str       # Routing target decided by SupervisorAgent ("planning", "research", "writing", etc.)
    supervisor_response: str   # Inline Q&A answer (set when next_step == "qa_response")
    interaction_mode: str      # "generation" | "modification" | "qa"
    modification_scope: str    # Scope of requested change, e.g. "ending", "character:Budi", "full"
    hitl_feedback: str         # Human approval / rejection text returned from the HITL gate
    bypass_supervisor: bool    # Skip supervisor LLM call and go directly to planning
    review_plan: bool          # True → pause after planning so human can review/adjust the plan before research starts
    supervisor_plan: List[str] # List of planned steps for multi-step execution (e.g. ['research', 'planning'])
    supervisor_plan_index: int # Current step index within the supervisor_plan
    # Recent UI/chat turns from client (e.g. {role, text}); replaced each interactive invoke
    user_chat_history: NotRequired[List[Dict[str, Any]]]
    # Completed stories from client session (title + excerpt) for supervisor recall across new runs
    prior_stories_archive: NotRequired[List[Dict[str, Any]]]

    # --- Reflexion Fields ---
    past_reflections: str      # Catatan refleksi dari sesi sebelumnya (diinjeksikan ke prompt Writer)
    reflection_generated: bool # Flag bahwa refleksi sudah disimpan ke database setelah sesi ini
    workflow_mode: str         # Mode eksperimen: "multi_agent" | "single_agent" | "baseline"

    # --- Director / Script Writer Fields ---
    draft_script: str          # Annotated screenplay .md content
    script_file_path: str      # Path to saved script file
    script_scene_count: int    # Number of scenes generated

