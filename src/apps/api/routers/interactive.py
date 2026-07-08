"""
Interactive Router — Supervisor-gated multi-turn workflow and Director script endpoints.

Endpoints:
  POST /interactive/chat        — SSE stream for supervisor-routed multi-turn workflow
  POST /interactive/route       — Single supervisor routing decision (no execution)
  POST /interactive/script      — Standalone dialogue script generation (DirectorAgent)
  GET  /interactive/thread/{id} — Thread state summary (story + script status)
"""

import json
import time
import uuid
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.runnables.config import RunnableConfig
from loguru import logger

from ..schemas import (
    InteractiveRequest,
    SupervisorRouteRequest,
    SupervisorRouteResponse,
    DirectorScriptRequest,
    DirectorScriptResponse,
)
from ..npc_registry import get_npc, build_npc_message

if TYPE_CHECKING:
    from workflows.story_agent.graph import create_interactive_workflow as _CIW
    from workflows.story_agent.agents.supervisor import SupervisorAgent as _SA
    from workflows.story_agent.agents.director import DirectorAgent as _DA
    from settings import StoryConfig as _SC
    from langgraph.types import Command as _Command
    from workflows.story_agent.state import StoryState

# Runtime imports — kept optional so tests that don't load the full graph still work
create_interactive_workflow: Any = None
SupervisorAgent: Any = None
DirectorAgent: Any = None
StoryConfig: Any = None
Command: Any = None
INTERACTIVE_AVAILABLE = False


def get_langfuse():
    return None


try:
    from workflows.story_agent.graph import create_interactive_workflow
    from workflows.story_agent.agents.supervisor import SupervisorAgent
    from workflows.story_agent.agents.director import DirectorAgent
    from settings import StoryConfig
    from langgraph.types import Command
    from workflows.story_agent.integrations.langfuse_client import get_langfuse  # type: ignore[assignment]
    INTERACTIVE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[API::GALAT] Could not import interactive modules: {e}")

router = APIRouter()

# Per-process workflow cache keyed by thread_id (MemorySaver lives in the app)
_workflow_instance = None


def _get_workflow():
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = create_interactive_workflow()
    return _workflow_instance


# =============================================================================
# SSE stream helpers
# =============================================================================

async def _interactive_sse_stream(request: InteractiveRequest) -> AsyncGenerator[str, None]:
    """Stream supervisor-gated multi-turn workflow events via SSE."""
    if not INTERACTIVE_AVAILABLE:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': 'Interactive workflow not available'})}\n\n"
        return

    thread_id = request.thread_id
    config: RunnableConfig = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
    start_time = time.time()

    yield f"event: SUPERVISOR::MULAI\ndata: {json.dumps({'thread_id': thread_id, 'message': 'Memproses permintaan...'})}\n\n"

    # Start a root Langfuse trace so downstream create_score calls have a trace_id
    langfuse = get_langfuse()
    trace_wrapper = None
    trace_id = ""

    try:
        if langfuse and langfuse.enabled:
            trace_wrapper = langfuse.trace(
                name="InteractiveWorkflow",
                session_id=thread_id,
                input_data=request.user_message,
                metadata={"thread_id": thread_id, "hitl_resume": bool(request.hitl_resume)},
            )
            trace_obj = trace_wrapper.__enter__()
            langfuse.set_parent_trace(trace_wrapper, session_id=thread_id)
            trace_id = trace_obj.trace_id
            logger.info(f"[INTERACTIVE::TRACE] Started root trace: {trace_id}")
    except Exception as _te:
        logger.warning(f"[INTERACTIVE::TRACE] Could not start Langfuse trace: {_te}")

    try:
        if getattr(request, 'model', None):
            workflow = create_interactive_workflow(model_name=request.model)
        else:
            workflow = _get_workflow()

        # Resume from HITL pause if resume token provided
        if request.hitl_resume:
            input_payload = Command(resume=request.hitl_resume)
            yield f"event: HITL::MELANJUTKAN\ndata: {json.dumps({'feedback': request.hitl_resume[:200]})}\n\n"
        else:
            history_norm: List[Dict[str, str]] = []
            if request.history:
                for item in request.history:
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role") or item.get("Role") or "").strip()
                    text = str(
                        item.get("text") or item.get("content") or item.get("message") or ""
                    ).strip()
                    if role and text:
                        history_norm.append({"role": role, "text": text[:8000]})

            prior_norm: List[Dict[str, str]] = []
            if request.prior_stories:
                for ps in request.prior_stories:
                    row = ps.model_dump() if hasattr(ps, "model_dump") else ps
                    if not isinstance(row, dict):
                        continue
                    tit = str(row.get("title") or "").strip()[:500]
                    ex = str(row.get("excerpt") or "").strip()[:6000]
                    if tit or ex:
                        prior_norm.append({"title": tit or "Tanpa judul", "excerpt": ex})
                prior_norm = prior_norm[-8:]

            input_payload = {
                "user_message": request.user_message,
                "language": request.language,
                "target_age": request.target_age or "",
                "story_length": request.story_length or StoryConfig.DEFAULT_STORY_LENGTH,
                "revision_count": 0,
                "messages": [],
                "session_id": thread_id,
                "trace_id": trace_id,
                "bypass_supervisor": False,
                "user_chat_history": history_norm,
                "prior_stories_archive": prior_norm,
            }
            if request.active_writers:
                input_payload["active_writers"] = request.active_writers

        # SSE node → tag mapping
        node_to_tag = {
            "supervisor_node":    "SUPERVISOR",
            "planning":           "PERENCANA",
            "planning_hitl_gate": "HITL_RENCANA",
            "research":           "RISET",
            "writer_text":      "PENULIS",
            "writer_diagram":   "DIAGRAM",
            "writer_director":  "SUTRADARA",
            "writer_image":     "GAMBAR",
            "merge_writers":    "GRAPH",
            "merge_production": "GRAPH",
            "production_gate":  "GRAPH",
            "critique":         "KRITIK",
            "revision_prep":    "GRAPH",
            "hitl_gate":        "HITL",
            "qa_response_node": "QA",
            "finalize":         "WORKFLOW",
            "ingest_sources":   "WORKFLOW",
        }

        final_state: dict = {}

        async for event in workflow.astream_events(input_payload, config=config, version="v2"):
            event_type = event.get("event", "")
            langgraph_node = event.get("metadata", {}).get("langgraph_node", "")
            tag = node_to_tag.get(langgraph_node)

            if not tag:
                continue

            if event_type == "on_chain_start":
                start_data = {
                    "agent": langgraph_node,
                    "status": "working",
                    "npc": get_npc(langgraph_node),
                    "message": build_npc_message(langgraph_node, "start", {}),
                }
                yield f"event: {tag}::MULAI\ndata: {json.dumps(start_data)}\n\n"

            elif event_type == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                # astream_events v2 can emit Pydantic models from inner chains
                # (e.g. SupervisorDecision from the structured LLM call).
                # Normalise to dict so every .get() below works safely.
                if hasattr(output, "model_dump"):
                    output = output.model_dump()
                elif not isinstance(output, dict):
                    output = {}
                if output:
                    final_state.update(output)

                event_data: dict = {"agent": langgraph_node, "status": "done"}

                # ------ node-specific payloads ------
                if langgraph_node == "supervisor_node":
                    event_data["next_step"] = output.get("supervisor_next", "")
                    event_data["interaction_mode"] = output.get("interaction_mode", "")
                    event_data["direct_response"] = output.get("supervisor_response", "")
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: SUPERVISOR::MEMUTUSKAN\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "qa_response_node":
                    event_data["answer"] = final_state.get("supervisor_response", "")
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: QA::MENJAWAB\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "planning_hitl_gate":
                    # Graph paused for plan review — surface plan details to client
                    outline = final_state.get("story_outline") or {}
                    plan_data = {
                        "thread_id": thread_id,
                        "type": "hitl_plan_review",
                        "draft_title": final_state.get("draft_title", ""),
                        "moral_message": final_state.get("moral_message", ""),
                        "characters": [
                            c.get("name", "?") for c in (final_state.get("characters") or [])[:6]
                        ],
                        "outline": {
                            "introduction": outline.get("introduction", ""),
                            "conflict":     outline.get("conflict", ""),
                            "climax":       outline.get("climax", ""),
                            "resolution":   outline.get("resolution", ""),
                        },
                        "message": "Tinjau rencana cerita. Kirim persetujuan untuk melanjutkan ke riset, atau berikan umpan balik untuk mengubah rencana.",
                        "npc": get_npc(langgraph_node),
                        "npc_message": build_npc_message(langgraph_node, "end", {}),
                    }
                    yield f"event: HITL_RENCANA::MENUNGGU\ndata: {json.dumps(plan_data)}\n\n"

                elif langgraph_node == "hitl_gate":
                    # Graph is now paused — tell client to send hitl_resume
                    hitl_data = {
                        "thread_id": thread_id,
                        "message": "Menunggu persetujuan manusia.",
                        "npc": get_npc(langgraph_node),
                        "npc_message": build_npc_message(langgraph_node, "end", {}),
                    }
                    yield f"event: HITL::MENUNGGU\ndata: {json.dumps(hitl_data)}\n\n"

                elif langgraph_node == "planning":
                    event_data["active_writers"] = output.get("active_writers", [])
                    event_data["characters"] = len(output.get("characters", []))
                    event_data["character_names"] = [
                        c.get("name", "?") for c in (output.get("characters") or [])[:3]
                    ]
                    event_data["draft_title"] = (
                        output.get("draft_title", "") or final_state.get("draft_title", "")
                    )
                    event_data["moral_message"] = output.get("moral_message", "")
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: PERENCANA::MERINCIKAN\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "research":
                    notes = output.get("research_notes", "")
                    sources = output.get("research_sources", [])
                    event_data["chars"] = len(notes)
                    event_data["source_count"] = len(sources) if sources else 0
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: RISET::MENEMUKAN_INFORMASI\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "writer_text":
                    draft = output.get("draft_content", "")
                    event_data["chars"] = len(draft)
                    event_data["words"] = len(draft.split())
                    event_data["draft_title"] = (
                        output.get("draft_title", "") or final_state.get("draft_title", "")
                    )
                    event_data["is_revision"] = final_state.get("revision_count", 0) > 0
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: PENULIS::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "writer_diagram":
                    event_data["has_diagram"] = bool(output.get("draft_diagram"))
                    event_data["diagram_type"] = output.get("diagram_type", "")
                    event_data["diagram_title"] = (
                        output.get("diagram_title", "") or final_state.get("diagram_title", "")
                    )
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: DIAGRAM::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "writer_image":
                    images = output.get("generated_images", [])
                    event_data["image_count"] = len(images)
                    event_data["images"] = [
                        {"path": img.get("file_path"), "success": img.get("success")}
                        for img in images
                    ]
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: GAMBAR::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "writer_director":
                    event_data["scene_count"] = output.get("script_scene_count", 0)
                    event_data["file_path"] = output.get("script_file_path", "")
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: SUTRADARA::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "critique":
                    raw_sc = output.get("structured_critique")
                    if isinstance(raw_sc, dict):
                        sc = raw_sc
                    elif raw_sc is not None and hasattr(raw_sc, "model_dump"):
                        sc = raw_sc.model_dump()
                    else:
                        sc = {}
                    event_data["quality_score"] = output.get("quality_score", 0)
                    event_data["decision"] = sc.get("decision", "")
                    event_data["edu_score"] = sc.get("educational_score", 0)
                    event_data["coherence_score"] = sc.get("coherence_score", 0)
                    coherence_issues = output.get("coherence_issues") or []
                    event_data["coherence_issues_count"] = len(coherence_issues)
                    event_data["coherence_issues"] = coherence_issues[:3]
                    event_data["ragas_scores"] = output.get("ragas_scores") or {}
                    event_data["npc"] = get_npc(langgraph_node)
                    event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                    yield f"event: KRITIK::MENGEVALUASI\ndata: {json.dumps(event_data)}\n\n"

                elif langgraph_node == "finalize":
                    elapsed = time.time() - start_time
                    final_data = {
                        "thread_id": thread_id,
                        "final_story": final_state.get("final_story", ""),
                        "draft_title": final_state.get("draft_title", ""),
                        "quality_score": final_state.get("quality_score", 0),
                        "revision_count": final_state.get("revision_count", 0),
                        "draft_diagram": final_state.get("draft_diagram", ""),
                        "script_file_path": final_state.get("script_file_path", ""),
                        "script_scene_count": final_state.get("script_scene_count", 0),
                        "generated_images": final_state.get("generated_images", []),
                        "elapsed_time": round(elapsed, 2),
                        "npc": get_npc(langgraph_node),
                        "message": build_npc_message(langgraph_node, "end", {"elapsed_time": round(elapsed, 2)}),
                    }
                    yield f"event: WORKFLOW::SELESAI\ndata: {json.dumps(final_data)}\n\n"

    except Exception as e:
        logger.error(f"[API::INTERAKTIF] Error: {e}")
        if trace_wrapper:
            try:
                trace_wrapper.__exit__(type(e), e, e.__traceback__)
            except Exception:
                pass
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': str(e)})}\n\n"
        return

    finally:
        # End the root trace so all scores are flushed regardless of exit path
        if trace_wrapper:
            try:
                trace_wrapper.__exit__(None, None, None)
            except Exception:
                pass


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/chat")
async def interactive_chat(request: InteractiveRequest):
    """
    Supervisor-gated multi-turn story workflow via SSE.

    - Send `user_message` + `thread_id` to start or continue a conversation.
    - On `HITL::MENUNGGU` event, send the same request again with `hitl_resume`
      set to the human's approval/rejection text.
    - The same `thread_id` persists state across turns (MemorySaver checkpointer).
    """
    return StreamingResponse(
        _interactive_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/route", response_model=SupervisorRouteResponse)
async def supervisor_route(request: SupervisorRouteRequest):
    """
    Ask the supervisor for a single routing decision without executing downstream agents.

    Useful for previewing what the supervisor would do given a message + current state,
    and for building interactive UIs that show routing decisions before committing.
    """
    if not INTERACTIVE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Supervisor not available")

    start = time.time()

    mock_state = {
        "user_message": request.user_message,
        "draft_content": request.draft_content or "",
        "final_story": request.final_story or "",
        "characters": request.characters or [],
        "moral_message": request.moral_message or "",
        "hitl_feedback": request.hitl_feedback or "",
        "language": request.language,
        "messages": [],
        "bypass_supervisor": False,
        "user_chat_history": [],
    }

    try:
        supervisor = SupervisorAgent()
        result = await supervisor.decide(cast("StoryState", mock_state))
    except Exception as e:
        logger.error(f"[API::ROUTE] Supervisor error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return SupervisorRouteResponse(
        next_step=result.get("supervisor_next", "planning"),
        interaction_mode=result.get("interaction_mode", "generation"),
        reasoning="",   # supervisor stores reasoning in the LLM call; not surfaced to state
        direct_response=result.get("supervisor_response") or None,
        modification_scope=result.get("modification_scope") or None,
        elapsed_time=round(time.time() - start, 2),
    )


@router.post("/script", response_model=DirectorScriptResponse)
async def generate_script(request: DirectorScriptRequest):
    """
    Standalone dialogue script generation via DirectorAgent.

    Converts an existing story into an annotated .md screenplay file.
    Does NOT require `ENABLE_DIRECTOR=true` — the feature flag governs
    graph-based auto-dispatch only; this endpoint always runs the agent directly.
    """
    if not INTERACTIVE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Director agent not available")

    start = time.time()
    session_id = request.session_id or f"script_{uuid.uuid4().hex[:12]}"

    state = {
        "active_writers": ["text", "director"],   # ensure skip guards pass
        "draft_content": request.story_content,
        "final_story": "",
        "characters": request.characters or [],
        "moral_message": request.moral_message or "",
        "theme": request.theme or "",
        "language": request.language,
        "session_id": session_id,
    }

    # Temporarily enable director just for this call
    original_flag = StoryConfig.ENABLE_DIRECTOR
    StoryConfig.ENABLE_DIRECTOR = True

    try:
        agent = DirectorAgent()
        result = await agent.direct(cast("StoryState", state))
    except Exception as e:
        logger.error(f"[API::SCRIPT] Director error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        StoryConfig.ENABLE_DIRECTOR = original_flag

    if not result.get("script_file_path"):
        raise HTTPException(status_code=500, detail="Script generation failed — no output produced")

    return DirectorScriptResponse(
        script_content=result.get("draft_script", ""),
        script_file_path=result.get("script_file_path", ""),
        scene_count=result.get("script_scene_count", 0),
        elapsed_time=round(time.time() - start, 2),
    )


@router.get("/thread/{thread_id}")
async def get_thread_state(thread_id: str):
    """
    Get a summary of the current state for a conversation thread.

    Returns story progress, script status, and any pending HITL gate info.
    """
    if not INTERACTIVE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Interactive workflow not available")

    try:
        workflow = _get_workflow()
        config: RunnableConfig = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
        snapshot = workflow.get_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found or error: {e}")

    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail=f"No state found for thread_id: {thread_id}")

    state = snapshot.values
    return {
        "thread_id": thread_id,
        "current_stage": state.get("current_stage", ""),
        "interaction_mode": state.get("interaction_mode", ""),
        "has_draft": bool(state.get("draft_content") or state.get("final_story")),
        "draft_title": state.get("draft_title", ""),
        "quality_score": state.get("quality_score", 0),
        "revision_count": state.get("revision_count", 0),
        "active_writers": state.get("active_writers", []),
        "has_diagram": bool(state.get("draft_diagram")),
        "has_script": bool(state.get("script_file_path")),
        "script_scene_count": state.get("script_scene_count", 0),
        "script_file_path": state.get("script_file_path", ""),
        "supervisor_next": state.get("supervisor_next", ""),
        "pending_hitl": bool(snapshot.next and "hitl_gate" in str(snapshot.next)),
    }
