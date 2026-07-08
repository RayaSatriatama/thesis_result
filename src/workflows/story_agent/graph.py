"""
Updated graph.py with parallel writers (Text, Image, Diagram) workflow.
Uses LangGraph Send API for conditional parallel dispatch based on active_writers.
Implements selective revision loop targeting only writers that need revision.
"""

from typing import Dict, Any, Literal, List
from loguru import logger
import warnings

from langgraph.graph import StateGraph, END
from langgraph.types import Send, interrupt
from langgraph.checkpoint.memory import MemorySaver
from .state import StoryState
from .agents.supervisor import SupervisorAgent
from .agents.researcher import ResearchAgent
from .agents.planner import PlannerAgent
from .agents.writer import WriterAgent
from .agents.writer_diagram import WriterDiagramAgent
from .agents.critic import CriticAgent
from .agents.image_generator import ImageGeneratorAgent
from .agents.director import DirectorAgent
from .agents.reflection import ReflectionGenerator, ReflectionRetriever

# Import settings
from settings import StoryConfig, LLMProviderConfig

# Import Langfuse for finalization scoring
try:
    from .integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None

# ---- Initialize Google Vertex AI only when the provider requires it ----
credentials = None
PROJECT_ID = None

if LLMProviderConfig.PROVIDER == "google_vertexai":
    warnings.filterwarnings("ignore", category=UserWarning, module="vertexai")
    try:
        import vertexai
        from google.oauth2 import service_account
        from config import CREDENTIALS_PATH, PROJECT_ID as _pid

        credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
        PROJECT_ID = _pid
        vertexai.init(project=PROJECT_ID, location=LLMProviderConfig.GOOGLE_LOCATION, credentials=credentials)
        logger.success("[GRAPH::INISIALISASI] Vertex AI initialized successfully")
    except Exception as e:
        logger.warning(f"[GRAPH::GALAT] Could not initialize Vertex AI: {e}")
        logger.info("[GRAPH::KONFIGURASI] Make sure config.py exists with CREDENTIALS_PATH and PROJECT_ID")
        credentials = None
        PROJECT_ID = None
else:
    logger.info(f"[GRAPH::KONFIGURASI] LLM provider: '{LLMProviderConfig.PROVIDER}' \u2014 Vertex AI tidak diinisialisasi")


def create_story_workflow(model_name: str | None = None):
    """
    Create the LangGraph workflow for story generation.

    New Flow (with parallel writers):
    1. START -> research
    2. research -> planning (planner decides active_writers)
    3. planning -> dispatch_to_writers (conditional Send)
       - Dispatches to active writers: text, image, diagram
    4. [writer_text, writer_image, writer_diagram] parallel
    5. merge_writers -> critique
    6. critique -> decision
    7. decision -> dispatch_to_writers (selective revision) OR finalize

    Uses LangGraph Send API for dynamic fan-out based on active_writers.

    Args:
        model_name: Override model name (e.g. 'gemma4:e4b' for Ollama).
                    If None, uses env default from LLMProviderConfig.
    """

    # Initialize agents with credentials
    supervisor = SupervisorAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    researcher = ResearchAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    planner = PlannerAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    writer_text = WriterAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    writer_diagram = WriterDiagramAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    writer_image = ImageGeneratorAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    director_agent = DirectorAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    critic = CriticAgent(model_name=model_name, credentials=credentials, project=PROJECT_ID)
    reflection_gen = ReflectionGenerator()
    reflection_ret = ReflectionRetriever()

    # Define the graph
    workflow = StateGraph(StoryState)

    # Add nodes
    workflow.add_node("research", researcher.research)
    workflow.add_node("planning", planner.plan)
    workflow.add_node("writer_text", writer_text.write)
    workflow.add_node("writer_diagram", writer_diagram.generate_diagram)
    workflow.add_node("writer_image", writer_image.generate_illustrations) # Now in "production" phase
    workflow.add_node("writer_director", director_agent.direct)
    workflow.add_node("production_gate", production_gate)
    workflow.add_node("merge_production", merge_production_results)
    workflow.add_node("merge_writers", merge_writer_results)
    workflow.add_node("critique", critic.critique)
    workflow.add_node("revision_prep", revision_prep) # New node to handle revision loop
    workflow.add_node("finalize", finalize_story)
    workflow.add_node("ingest_sources", researcher.finalize_ingestion)
    # Reflexion nodes
    workflow.add_node("retrieve_reflections", reflection_ret.retrieve)
    workflow.add_node("generate_reflection", reflection_gen.generate_and_store)

    # Define edges - Order: Planner -> Researcher -> Writers
    workflow.set_entry_point("planning")  # Start with planner

    # Sequential flow: planning -> research -> retrieve_reflections -> parallel writers
    workflow.add_edge("planning", "research")

    # After research, retrieve past reflections before dispatching to writers
    workflow.add_edge("research", "retrieve_reflections")
    workflow.add_conditional_edges(
        "retrieve_reflections",
        dispatch_to_writers,
        ["writer_text", "writer_diagram"]
    )

    # All writer branches converge to merge node
    workflow.add_edge("writer_text", "merge_writers")
    workflow.add_edge("writer_diagram", "merge_writers")

    # After merge, go to critique
    workflow.add_edge("merge_writers", "critique")

    # After critique, decide to revise or finalize (production)
    workflow.add_conditional_edges(
        "critique",
        should_continue_or_finalize,
        {
            "dispatch_writers": "revision_prep",  # Loop back through revision prep
            "production": "production_gate",       # Move to production dispatch if approved
            "research": "research"                 # Loop back to research if gaps found
        }
    )

    # Revision prep connects back to writers
    workflow.add_conditional_edges(
        "revision_prep",
        dispatch_to_writers,
        ["writer_text", "writer_diagram"]
    )

    # Production dispatch: writer_image always, writer_director if enabled
    workflow.add_conditional_edges(
        "production_gate",
        dispatch_to_production,
        ["writer_image", "writer_director"]
    )
    workflow.add_edge("writer_image", "merge_production")
    workflow.add_edge("writer_director", "merge_production")
    workflow.add_edge("merge_production", "finalize")

    # Finalize -> generate_reflection -> Ingestion -> END
    workflow.add_edge("finalize", "generate_reflection")
    workflow.add_edge("generate_reflection", "ingest_sources")
    workflow.add_edge("ingest_sources", END)

    return workflow.compile()


def create_single_agent_workflow():
    """
    Create a simplified Single Agent workflow for ablation study comparison.

    Architecture (Single Agent):
        START -> research -> writer_text -> finalize -> ingest_sources -> END

    Differences from multi-agent workflow:
    - No PlannerAgent (theme passed directly to ResearchAgent)
    - No CriticAgent revision loop (writer runs exactly once)
    - No parallel writer dispatch (text only)
    - No production phase (no image/director)
    - LightRAG retrieval still active (distinguishes from Baseline)
    - Langfuse traces tagged with workflow_mode="single_agent"

    Used for: Scopus paper ablation study (Baseline vs Single vs Multi).
    """
    researcher = ResearchAgent(credentials=credentials, project=PROJECT_ID)
    writer_text = WriterAgent(credentials=credentials, project=PROJECT_ID)

    async def single_research(state: StoryState) -> Dict[str, Any]:
        """Research node that signals LightRAG-only mode (no web search)."""
        result = await researcher.research(state)
        result["workflow_mode"] = "single_agent"
        return result

    async def single_write(state: StoryState) -> Dict[str, Any]:
        """Writer node: one-shot generation without outline or revision context."""
        patched = dict(state)
        patched.setdefault("active_writers", ["text"])
        patched.setdefault("revision_count", 0)
        patched.setdefault("story_outline", {})
        patched.setdefault("characters", [])
        patched.setdefault("moral_message", "")
        return await writer_text.write(patched)

    workflow = StateGraph(StoryState)

    workflow.add_node("research", single_research)
    workflow.add_node("writer_text", single_write)
    workflow.add_node("finalize", finalize_story)
    workflow.add_node("ingest_sources", researcher.finalize_ingestion)

    workflow.set_entry_point("research")
    workflow.add_edge("research", "writer_text")
    workflow.add_edge("writer_text", "finalize")
    workflow.add_edge("finalize", "ingest_sources")
    workflow.add_edge("ingest_sources", END)

    logger.info("[GRAPH::SINGLE] Single Agent workflow compiled.")
    return workflow.compile()


def dispatch_to_writers(state: StoryState) -> List[Send]:
    """
    Dispatch to parallel writers using LangGraph Send API.

    Dispatches based on:
    - active_writers list from Planner
    - Per-writer revision flags (on revision passes)

    Returns:
        List of Send objects for dynamic fan-out
    """
    revision_count = state.get("revision_count", 0)
    active_writers = state.get("active_writers", ["text"])

    sends = []

    # Text writer
    if "text" in active_writers:
        if revision_count == 0 or state.get("needs_text_revision", True):
            sends.append(Send("writer_text", state))
            logger.debug("[GRAPH::DISPATCH] Dispatching to writer_text")

    # Image writer - REMOVED from initial dispatch, moved to 'production' phase
    # if "image" in active_writers:
    #     if revision_count == 0 or state.get("needs_image_revision", False):
    #         sends.append(Send("writer_image", state))
    #         logger.debug("[GRAPH::DISPATCH] Dispatching to writer_image")

    # Diagram writer
    if "diagram" in active_writers:
        if revision_count == 0 or state.get("needs_diagram_revision", False):
            sends.append(Send("writer_diagram", state))
            logger.debug("[GRAPH::DISPATCH] Dispatching to writer_diagram")

    if not sends:
        # Fallback: at least run text writer
        sends.append(Send("writer_text", state))

    # Final state preparation
    logger.info(f"[GRAPH::MENGIRIM] Parallel dispatch: {len(sends)} writer(s) - {[s.node for s in sends]}")
    return sends


def merge_writer_results(state: StoryState) -> Dict[str, Any]:
    """
    Merge results from parallel writers.

    This node waits for all active writer branches to complete.
    LangGraph automatically aggregates state updates from parallel nodes.
    """
    active_writers = state.get("active_writers", ["text"])

    # Log    # Merge results
    logger.info(f"[GRAPH::MENGGABUNG] Parallel writers complete:")

    if "text" in active_writers:
        draft_len = len(state.get("draft_content", ""))
        logger.info(f"[GRAPH::MENGGABUNG]    Text: {draft_len} characters")

    if "image" in active_writers:
        images = state.get("generated_images", [])
        success = sum(1 for img in images if img.get("success", False))
        logger.info(f"[GRAPH::MERGE]    Image: {success}/{len(images)} generated")

    if "diagram" in active_writers:
        diagram = state.get("draft_diagram", "")
        has_png = bool(state.get("diagram_image_path", ""))
        logger.info(f"[GRAPH::MENGGABUNG]    Diagram: {'YES' if diagram else 'NO'} code, {'YES' if has_png else 'NO'} PNG")

    # No state changes needed - just a synchronization point
    return {}


def should_continue_or_finalize(state: StoryState) -> Literal["dispatch_writers", "production", "research"]:
    """
    Determine if we should revise, research more, or finalize.
    """
    revision_count = state.get("revision_count", 0)
    max_revisions = StoryConfig.MAX_REVISIONS

    # Get critic's decision
    structured_critique = state.get("structured_critique", {})
    critic_decision = structured_critique.get("decision", "REVISE")

    # Safety check: max revisions reached
    if revision_count >= max_revisions:
        logger.info(f"[GRAPH::MEMUTUSKAN] Batas revisi tercapai ({max_revisions}). Lanjut ke produksi.")
        return "production"

    # Use critic's decision
    if critic_decision == "NEED_MORE_RESEARCH":
        logger.warning(f"[GRAPH::MEMUTUSKAN] Data kurang lengkap. Kembali ke riset.")
        return "research"
    elif critic_decision.startswith("APPROVE"):
        logger.success(f"[GRAPH::MEMUTUSKAN] Kualitas cerita sudah bagus! Lanjut ke produksi.")
        return "production"
    else:
        logger.info(f"[GRAPH::MEMUTUSKAN] Perlu perbaikan (Revisi {revision_count + 1}/{max_revisions})...")
        return "dispatch_writers"

def revision_prep(state: StoryState) -> Dict[str, Any]:
    """
    Pass-through node to prepare for revision loop.
    Logging and potential state adjustment.
    """
    logger.info("[GRAPH::REVISI] Menyiapkan rencana perbaikan...")
    return {}


def dispatch_to_production(state: StoryState) -> List[Send]:
    """
    Production-phase parallel dispatch using LangGraph Send API.

    Always dispatches writer_image. Also dispatches writer_director when
    ENABLE_DIRECTOR is True and 'director' is listed in active_writers.

    Returns:
        List of Send objects for dynamic fan-out to production writers.
    """
    active_writers = state.get("active_writers", ["text"])
    sends = [Send("writer_image", state)]

    if StoryConfig.ENABLE_DIRECTOR and "director" in active_writers:
        sends.append(Send("writer_director", state))
        logger.debug("[GRAPH::PRODUKSI] Dispatching writer_image + writer_director")
    else:
        logger.debug("[GRAPH::PRODUKSI] Dispatching writer_image only")

    return sends


def production_gate(state: StoryState) -> Dict[str, Any]:
    """
    Pass-through synchronization node before parallel production dispatch.
    Mirrors the pattern of revision_prep for LangGraph conditional edge routing.
    """
    logger.info("[GRAPH::PRODUKSI] Masuk fase produksi — mengirim ke writer paralel.")
    return {}


def merge_production_results(state: StoryState) -> Dict[str, Any]:
    """
    Merge results from parallel production writers (writer_image, writer_director).
    LangGraph aggregates state updates automatically; this node is a sync point.
    """
    active_writers = state.get("active_writers", ["text"])

    logger.info("[GRAPH::PRODUKSI] Production writers selesai:")

    if "image" in active_writers:
        images = state.get("generated_images", [])
        success = sum(1 for img in images if img.get("success", False))
        logger.info(f"[GRAPH::PRODUKSI]   Image: {success}/{len(images)} generated")

    if "director" in active_writers and StoryConfig.ENABLE_DIRECTOR:
        script_path = state.get("script_file_path", "")
        scene_count = state.get("script_scene_count", 0)
        logger.info(
            f"[GRAPH::PRODUKSI]   Skrip: {scene_count} scene"
            + (f", {script_path}" if script_path else " (tidak tersimpan)")
        )

    return {}


def finalize_story(state: StoryState) -> Dict[str, Any]:
    """
    Finalize the story and prepare output.

    """
    logger.info("[GRAPH::SELESAI] STORY GENERATION COMPLETE!")
    logger.info(f"[GRAPH::STATUS] Quality Score: {state.get('quality_score', 0.0)}/5")
    logger.info(f"[GRAPH::STATUS] Revisions: {state.get('revision_count', 0)}")

    active_writers = state.get("active_writers", ["text"])

    # Report text
    if "text" in active_writers:
        draft_len = len(state.get("draft_content", ""))
        logger.info(f"[GRAPH::STATUS] Story Text: {draft_len} characters")

    # Report generated images
    if "image" in active_writers:
        generated_images = state.get("generated_images", [])
        if generated_images:
            success_count = sum(1 for img in generated_images if img.get("success", False))
            logger.info(f"[GRAPH::STATUS] Generated Images: {success_count}/{len(generated_images)}")
            coherence_issues = state.get("coherence_issues", [])
            if coherence_issues:
                logger.warning(f"\n  Coherence Issues Detected: {len(coherence_issues)}")
                for i, issue in enumerate(coherence_issues[:5], 1):  # Show first 5
                    if isinstance(issue, dict):
                        logger.warning(f"   {i}. {issue.get('issue_type', 'Unknown')}: {issue.get('description', '')[:100]}")
                    else:
                        logger.warning(f"   {i}. {issue}")
            for img in generated_images:
                if img.get("success") and img.get("file_path"):
                    logger.info(f"[GRAPH::STATUS]   - {img['file_path']}")

    # Report diagram
    if "diagram" in active_writers:
        diagram_path = state.get("diagram_image_path", "")
        if diagram_path:
            logger.info(f"[GRAPH::STATUS] Diagram: {diagram_path}")

    return {
        "final_story": state.get("draft_content", ""),
        "draft_title": state.get("draft_title", ""),
        "current_stage": "complete"
    }


# ===========================================================================
# Interactive workflow helpers (Phases 3/4/6)
# ===========================================================================

def planning_hitl_gate(state: StoryState) -> Dict[str, Any]:
    """
    Human-in-the-loop gate after planning, before research begins.
    Only reached when review_plan=True — i.e. the Supervisor detected that the
    user wants to review/approve the generated plan before writing starts.
    Human can approve (→ research) or request changes (→ supervisor re-routes
    back to planning with the feedback in hitl_feedback).
    """
    story_outline = state.get("story_outline") or {}
    characters = state.get("characters") or []
    moral_message = state.get("moral_message", "")
    draft_title = state.get("draft_title", "")

    human_input = interrupt({
        "type": "hitl_plan_review",
        "draft_title": draft_title,
        "moral_message": moral_message,
        "characters": [c.get("name", "?") for c in characters[:6]],
        "outline": {
            "introduction": story_outline.get("introduction", ""),
            "conflict":     story_outline.get("conflict", ""),
            "climax":       story_outline.get("climax", ""),
            "resolution":   story_outline.get("resolution", ""),
        },
        "message": (
            "Tinjau rencana cerita di atas. "
            "Kirim persetujuan untuk melanjutkan ke riset, "
            "atau berikan umpan balik untuk mengubah rencana."
        ),
    })

    logger.info(f"[GRAPH::HITL_PLAN] Human plan feedback received: {str(human_input)[:120]}")
    # Clear review_plan so the next supervisor decision starts clean
    return {"hitl_feedback": str(human_input), "review_plan": False}


def route_after_planning(state: StoryState) -> str:
    """
    Conditional edge after planning.
    Default path is straight to research.
    Only diverts to planning_hitl_gate when the Supervisor explicitly set review_plan=True.
    """
    if state.get("review_plan"):
        logger.info("[GRAPH::PLAN] review_plan=True → pausing for human plan review")
        return "planning_hitl_gate"
    return "research"


def hitl_gate(state: StoryState) -> Dict[str, Any]:
    """
    Human-in-the-loop gate after modification critique.
    Pauses graph execution with interrupt() and waits for human approval/rejection.
    Requires a LangGraph checkpointer (MemorySaver) to persist state across the pause.
    """
    structured_critique = state.get("structured_critique", {})
    critique_feedback = state.get("critique_feedback", "")
    quality_score = state.get("quality_score", 0.0)
    draft_content = state.get("draft_content", "")

    human_input = interrupt({
        "type": "hitl_critique_review",
        "quality_score": quality_score,
        "critique_summary": critique_feedback[:400] if critique_feedback else "",
        "draft_preview": draft_content[:600] if draft_content else "",
        "critic_decision": structured_critique.get("decision", ""),
    })

    logger.info(f"[GRAPH::HITL] Human feedback received: {str(human_input)[:120]}")
    return {"hitl_feedback": str(human_input)}


def qa_response_node(state: StoryState) -> Dict[str, Any]:
    """
    Pass-through node for inline Q&A responses.
    The supervisor already computed the answer in supervisor_response;
    this node surfaces it as a graph step so it appears in traces/logs.
    """
    response = state.get("supervisor_response", "")
    logger.info(f"[GRAPH::QA] → {response[:200]}")
    return {}


def route_from_supervisor(state: StoryState) -> str:
    """
    Conditional edge function: reads supervisor_next from state and
    returns the target node name (or 'FINISH' for the END mapping).
    """
    return state.get("supervisor_next", "planning")


def route_after_critique_interactive(
    state: StoryState,
) -> Literal["dispatch_writers", "production", "research", "hitl_gate"]:
    """
    Critique routing for the interactive workflow.
    In modification mode, always pause for HITL instead of auto-looping.
    In generation mode, delegates to the existing should_continue_or_finalize logic.
    """
    if state.get("interaction_mode") == "modification":
        logger.info("[GRAPH::INTERAKTIF] Mode modifikasi → HITL gate")
        return "hitl_gate"
    return should_continue_or_finalize(state)


def create_interactive_workflow(model_name: str | None = None):
    """
    Create the LangGraph workflow for interactive story generation.

    Entry point is supervisor_node, which handles:
    - Fresh story generation (routes to planning; bypass with bypass_supervisor=True)
    - Targeted story modification (routes to writing / revision_prep)
    - Inline Q&A (answers directly, no sub-agent call)
    - HITL-gated critique after modifications

    Multi-turn usage pattern (with MemorySaver checkpointer):
        app = create_interactive_workflow()
        config = {"configurable": {"thread_id": "session-abc"}}
        # Turn 1 — new story
        result = app.invoke({"user_message": "Buat cerita tentang ..."}, config)
        # Turn 2 — modify
        result = app.invoke({"user_message": "Ubah akhir ceritanya"}, config)
        # Turn 3 — resume after interrupt() in hitl_gate
        result = app.invoke(None, config, command=Command(resume="Setuju, lanjutkan"))

    New nodes: supervisor_node, hitl_gate, qa_response_node
    All 10 original nodes are reused without modification.
    """
    supervisor = SupervisorAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    researcher = ResearchAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    planner = PlannerAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    writer_text = WriterAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    writer_diagram = WriterDiagramAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    writer_image = ImageGeneratorAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    director_agent = DirectorAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    critic = CriticAgent(credentials=credentials, project=PROJECT_ID, model_name=model_name)
    reflection_gen = ReflectionGenerator(model_name=model_name)
    reflection_ret = ReflectionRetriever()

    # Async node wrapper that captures supervisor instance
    async def supervisor_node_fn(state: StoryState) -> Dict[str, Any]:
        return await supervisor.decide(state)

    workflow = StateGraph(StoryState)

    # --- Supervisor + interactive nodes ---
    workflow.add_node("supervisor_node", supervisor_node_fn)
    workflow.add_node("hitl_gate", hitl_gate)
    workflow.add_node("qa_response_node", qa_response_node)

    # --- Reuse all original nodes ---
    workflow.add_node("planning", planner.plan)
    workflow.add_node("research", researcher.research)
    workflow.add_node("writer_text", writer_text.write)
    workflow.add_node("writer_diagram", writer_diagram.generate_diagram)
    workflow.add_node("writer_image", writer_image.generate_illustrations)
    workflow.add_node("writer_director", director_agent.direct)
    workflow.add_node("production_gate", production_gate)
    workflow.add_node("merge_production", merge_production_results)
    workflow.add_node("merge_writers", merge_writer_results)
    workflow.add_node("critique", critic.critique)
    workflow.add_node("revision_prep", revision_prep)
    workflow.add_node("finalize", finalize_story)
    workflow.add_node("ingest_sources", researcher.finalize_ingestion)
    # Reflexion nodes
    workflow.add_node("retrieve_reflections", reflection_ret.retrieve)
    workflow.add_node("generate_reflection", reflection_gen.generate_and_store)

    # --- Entry point ---
    workflow.set_entry_point("supervisor_node")

    # --- Supervisor routing ---
    workflow.add_conditional_edges(
        "supervisor_node",
        route_from_supervisor,
        {
            "planning":        "planning",
            "research":        "research",
            "writing":         "revision_prep",   # targets writers via dispatch_to_writers
            "critique":        "critique",
            "finalize":        "finalize",
            "qa_response":     "qa_response_node",
            "director":        "production_gate",  # route to production for director script
            "FINISH":          END,
        },
    )

    # --- Generation flow: planning → (optional HITL plan review) → research → parallel writers ---
    workflow.add_node("planning_hitl_gate", planning_hitl_gate)
    workflow.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "planning_hitl_gate": "planning_hitl_gate",
            "research":           "research",
        },
    )
    # After plan review human feedback is stored; supervisor re-reads it and
    # decides: proceed to research, or re-plan with requested changes.
    workflow.add_edge("planning_hitl_gate", "supervisor_node")
    workflow.add_edge("research", "retrieve_reflections")
    workflow.add_conditional_edges(
        "retrieve_reflections",
        dispatch_to_writers,
        ["writer_text", "writer_diagram"],
    )

    # --- Writers → merge → critique ---
    workflow.add_edge("writer_text", "merge_writers")
    workflow.add_edge("writer_diagram", "merge_writers")
    workflow.add_edge("merge_writers", "critique")

    # --- Critique routing (interactive) ---
    workflow.add_conditional_edges(
        "critique",
        route_after_critique_interactive,
        {
            "dispatch_writers": "revision_prep",
            "production":       "production_gate",
            "research":         "research",
            "hitl_gate":        "hitl_gate",
        },
    )

    # --- Revision loop ---
    workflow.add_conditional_edges(
        "revision_prep",
        dispatch_to_writers,
        ["writer_text", "writer_diagram"],
    )

    # --- Production path: dispatch + merge ---
    workflow.add_conditional_edges(
        "production_gate",
        dispatch_to_production,
        ["writer_image", "writer_director"]
    )
    workflow.add_edge("writer_image", "merge_production")
    workflow.add_edge("writer_director", "merge_production")
    workflow.add_edge("merge_production", "finalize")

    # --- Finalize → generate_reflection → ingest → END (caller reinvokes for next turn) ---
    workflow.add_edge("finalize", "generate_reflection")
    workflow.add_edge("generate_reflection", "ingest_sources")
    workflow.add_edge("ingest_sources", END)

    # --- HITL gate → supervisor (human feedback read on next decide()) ---
    workflow.add_edge("hitl_gate", "supervisor_node")

    # --- Q&A pass-through → END (caller reinvokes for follow-up) ---
    workflow.add_edge("qa_response_node", END)

    return workflow.compile(checkpointer=MemorySaver())