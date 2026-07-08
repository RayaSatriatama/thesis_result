"""
Workflow Router - Full story generation with SSE streaming
"""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from ..schemas import WorkflowRequest
from ..npc_registry import get_npc, build_npc_message
# Workflow API router - Triggering reload

# Import workflow
try:
    from workflows.story_agent.graph import create_story_workflow, create_single_agent_workflow
    from workflows.story_agent.story_canvas import StoryCanvas
    from settings import StoryConfig
    from workflows.story_agent.integrations.langfuse_client import get_langfuse, LangfuseGraphCallbackHandler
    WORKFLOW_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[API::GALAT] Could not import workflow: {e}")
    WORKFLOW_AVAILABLE = False
    get_langfuse = lambda: None

# Import Blackboard architecture (C4 -- ablation study)
try:
    from workflows.arch_blackboard.graph import create_blackboard_workflow
    BLACKBOARD_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[API::GALAT] Could not import blackboard workflow: {e}")
    BLACKBOARD_AVAILABLE = False

# Import Debate architecture
try:
    from workflows.story_agent_debate.graph import create_debate_workflow
    DEBATE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[API::GALAT] Could not import debate workflow: {e}")
    DEBATE_AVAILABLE = False

# Import STORM architecture
try:
    from workflows.story_agent_storm.graph import create_storm_workflow
    STORM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[API::GALAT] Could not import storm workflow: {e}")
    STORM_AVAILABLE = False

router = APIRouter()

# Store active jobs for status checking
active_jobs = {}

# Singleton workflow instance — built once at startup, reused for every request.
_workflow_instance = None

# Singleton for single-agent workflow (ablation study).
_single_workflow_instance = None

# Singleton for Blackboard workflow (C4 -- ablation study).
_blackboard_workflow_instance = None

# Singleton for Debate workflow.
_debate_workflow_instance = None

# Singleton for STORM workflow.
_storm_workflow_instance = None


def _get_workflow():
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = create_story_workflow()
    return _workflow_instance


def _get_single_agent_workflow():
    global _single_workflow_instance
    if _single_workflow_instance is None:
        _single_workflow_instance = create_single_agent_workflow()
    return _single_workflow_instance


def _get_blackboard_workflow():
    global _blackboard_workflow_instance
    if _blackboard_workflow_instance is None:
        _blackboard_workflow_instance = create_blackboard_workflow()
    return _blackboard_workflow_instance


def _get_debate_workflow():
    global _debate_workflow_instance
    if _debate_workflow_instance is None:
        _debate_workflow_instance = create_debate_workflow()
    return _debate_workflow_instance


_storm_workflow_instances = {}

def _get_storm_workflow(language: str = "id"):
    if language not in _storm_workflow_instances:
        _storm_workflow_instances[language] = create_storm_workflow(language=language)
    return _storm_workflow_instances[language]


async def generate_sse_stream(request: WorkflowRequest) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream from workflow execution.
    Uses existing [AGENT::ACTION] tag format for events.
    """
    if not WORKFLOW_AVAILABLE:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': 'Workflow not available'})}\n\n"
        return

    job_id = f"story_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    # Send initial event
    yield f"event: WORKFLOW::MULAI\ndata: {json.dumps({'job_id': job_id, 'message': 'Memulai pembuatan cerita...'})}\n\n"

    try:
        # Use custom model instance if specified, otherwise reuse singleton
        if request.model:
            workflow = create_story_workflow(model_name=request.model)
        else:
            workflow = _get_workflow()

        # Prepare initial state
        initial_state = {
            "user_message": request.prompt,
            "theme": request.prompt,
            "target_age": request.target_age or "",
            "language": request.language,
            "story_length": request.story_length or StoryConfig.DEFAULT_STORY_LENGTH,
            "learning_objectives": "",
            "story_style": "",
            "narrative_style": "campuran",
            "emotional_tone": "",
            "enriched_context": "",
            "user_characters": "",
            "user_setting": "",
            "current_stage": "planning",
            "messages": [],
            "revision_count": 0,
            "revision_history": [],
            "quality_score": 0.0,
            "session_id": job_id,
            "total_tokens": 0
        }

        # If user specified active_writers, use them
        if request.active_writers:
            initial_state["active_writers"] = request.active_writers

        final_state = {}

        # Initialize Langfuse Trace
        langfuse = get_langfuse()
        trace_wrapper = None

        try:
            config = {"run_name": "StoryGenerationWorkflow"}
            if langfuse and langfuse.enabled:
                trace_wrapper = langfuse.trace(
                    name="StoryGenerationWorkflow",
                    session_id=job_id,
                    user_id=request.user_id if hasattr(request, 'user_id') else "user_v1",
                    input_data=request.prompt,  # Set main input
                    metadata={
                        "job_id": job_id,
                        "active_writers": request.active_writers,
                        "target_age": request.target_age,
                        "theme": request.prompt
                    }
                )
                # Start trace (enter context)
                trace = trace_wrapper.__enter__()

                # Set as parent for all agents (singleton state)
                langfuse.set_parent_trace(trace_wrapper, session_id=job_id)

                # Add trace_id to state for distributed propagation
                initial_state["trace_id"] = trace.trace_id
                logger.info(f"[WORKFLOW::TRACE] Started root trace: {trace.trace_id}")

                # langfuse langchain CallbackHandler disabled to prevent internal spans like ChatOpenAI/RunnableSequence
                pass

            # Stream events from workflow
            async for event in workflow.astream_events(initial_state, config=config, version="v2"):
                event_type = event.get("event", "")
                name = event.get("name", "")
                langgraph_node = event.get("metadata", {}).get("langgraph_node", "")

                # Map node names to SSE event tags
                node_to_tag = {
                    "research": "RISET",
                    "planning": "PERENCANA",
                    "writer_text": "PENULIS",
                    "writer_image": "GAMBAR",
                    "writer_diagram": "DIAGRAM",
                    "merge_writers": "GRAPH",
                    "critique": "KRITIK",
                    "finalize": "WORKFLOW"
                }

                # Handle node start
                if event_type == "on_chain_start" and langgraph_node in node_to_tag:
                    tag = node_to_tag[langgraph_node]
                    start_data = {
                        "agent": langgraph_node,
                        "status": "working",
                        "npc": get_npc(langgraph_node),
                        "message": build_npc_message(langgraph_node, "start", {}),
                    }
                    yield f"event: {tag}::MULAI\ndata: {json.dumps(start_data)}\n\n"

                # Handle node completion
                elif event_type == "on_chain_end" and langgraph_node in node_to_tag:
                    output = event.get("data", {}).get("output", {})
                    tag = node_to_tag[langgraph_node]

                    if isinstance(output, dict):
                        final_state.update(output)

                        # Build event data based on agent
                        event_data = {"agent": langgraph_node, "status": "done"}

                        if langgraph_node == "research":
                            notes = output.get("research_notes", "")
                            sources = output.get("research_sources", []) or []
                            event_data["chars"] = len(notes)
                            event_data["source_count"] = len(sources)
                            event_data["npc"] = get_npc(langgraph_node)
                            event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                            event_data["raw_output"] = {
                                "research_notes": notes,
                                "research_sources": sources,
                                "questions": output.get("questions", []),
                            }
                            yield f"event: RISET::MENEMUKAN_INFORMASI\ndata: {json.dumps(event_data)}\n\n"

                        elif langgraph_node == "planning":
                            event_data["active_writers"] = output.get("active_writers", [])
                            event_data["characters"] = len(output.get("characters", []))
                            event_data["character_names"] = [
                                c.get("name", "?") for c in (output.get("characters") or [])[:3]
                            ]
                            event_data["draft_title"] = output.get("draft_title", "")
                            event_data["moral_message"] = output.get("moral_message", "")
                            event_data["npc"] = get_npc(langgraph_node)
                            event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                            event_data["raw_output"] = {
                                "theme": output.get("theme", ""),
                                "target_age": output.get("target_age", ""),
                                "learning_objectives": output.get("learning_objectives", ""),
                                "story_style": output.get("story_style", ""),
                                "narrative_style": output.get("narrative_style", ""),
                                "emotional_tone": output.get("emotional_tone", ""),
                                "story_length": output.get("story_length", ""),
                                "draft_title": output.get("draft_title", ""),
                                "story_outline": output.get("story_outline", {}),
                                "characters": output.get("characters", []),
                                "moral_message": output.get("moral_message", ""),
                                "active_writers": output.get("active_writers", []),
                                "setting_ideas": output.get("setting_ideas", ""),
                                "character_ideas": output.get("character_ideas", ""),
                                "writer_reasoning": output.get("writer_reasoning", ""),
                            }
                            yield f"event: PERENCANA::MERINCIKAN\ndata: {json.dumps(event_data)}\n\n"

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
                            event_data["raw_output"] = {
                                "draft_title": event_data["draft_title"],
                                "draft_content": draft,
                            }
                            yield f"event: PENULIS::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                        elif langgraph_node == "writer_diagram":
                            diagram = output.get("draft_diagram", "")
                            event_data["has_diagram"] = bool(diagram)
                            event_data["diagram_type"] = output.get("diagram_type", "")
                            event_data["diagram_title"] = (
                                output.get("diagram_title", "") or final_state.get("diagram_title", "")
                            )
                            event_data["npc"] = get_npc(langgraph_node)
                            event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                            event_data["raw_output"] = {
                                "draft_diagram": diagram,
                                "diagram_type": event_data["diagram_type"],
                                "diagram_title": event_data["diagram_title"],
                            }
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
                            event_data["raw_output"] = {
                                "generated_images": images,
                            }
                            yield f"event: GAMBAR::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                        elif langgraph_node == "merge_writers":
                            event_data["npc"] = get_npc(langgraph_node)
                            event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                            yield f"event: GRAPH::MENGGABUNG\ndata: {json.dumps(event_data)}\n\n"

                        elif langgraph_node == "critique":
                            raw_sc = output.get("structured_critique")
                            if isinstance(raw_sc, dict):
                                sc = raw_sc
                            elif raw_sc is not None and hasattr(raw_sc, "model_dump"):
                                sc = raw_sc.model_dump()
                            else:
                                sc = {}
                            coherence_issues = output.get("coherence_issues") or []
                            event_data["quality_score"] = output.get("quality_score", 0)
                            event_data["decision"] = sc.get("decision", output.get("critique_decision", ""))
                            event_data["edu_score"] = sc.get("educational_score", 0)
                            event_data["coherence_score"] = sc.get("coherence_score", 0)
                            event_data["coherence_issues_count"] = len(coherence_issues)
                            event_data["coherence_issues"] = coherence_issues[:3]
                            event_data["ragas_scores"] = output.get("ragas_scores") or {}
                            event_data["npc"] = get_npc(langgraph_node)
                            event_data["message"] = build_npc_message(langgraph_node, "end", event_data)
                            event_data["raw_output"] = {
                                "quality_score": event_data["quality_score"],
                                "structured_critique": sc,
                                "coherence_issues": coherence_issues,
                                "ragas_scores": event_data["ragas_scores"],
                            }
                            yield f"event: KRITIK::MENGEVALUASI\ndata: {json.dumps(event_data)}\n\n"

                        elif langgraph_node == "finalize":
                            # Final event with full output
                            elapsed = time.time() - start_time
                            final_data = {
                                "job_id": job_id,
                                "final_story": final_state.get("final_story", ""),
                                "draft_title": final_state.get("draft_title", ""),
                                "quality_score": final_state.get("quality_score", 0),
                                "revision_count": final_state.get("revision_count", 0),
                                "draft_diagram": final_state.get("draft_diagram", ""),
                                "diagram_title": final_state.get("diagram_title", ""),
                                "generated_images": final_state.get("generated_images", []),
                                "elapsed_time": round(elapsed, 2),
                                "npc": get_npc(langgraph_node),
                                "message": build_npc_message(langgraph_node, "end", {"elapsed_time": round(elapsed, 2)}),
                            }
                            yield f"event: WORKFLOW::SELESAI\ndata: {json.dumps(final_data)}\n\n"

                            # Update root trace output in Langfuse
                            if langfuse and langfuse.enabled:
                                try:
                                    langfuse.client.update_current_trace(
                                        output=final_data
                                    )
                                except Exception as trace_err:
                                    logger.warning(f"Failed to update root trace output: {trace_err}")

        finally:
            # Cleanup Trace
            if trace_wrapper:
                try:
                    if langfuse:
                        langfuse.clear_parent_trace()
                    trace_wrapper.__exit__(None, None, None)
                    logger.info("[WORKFLOW::TRACE] Root trace closed")
                except Exception as e:
                    logger.error(f"[WORKFLOW::TRACE] Error closing trace: {e}")

    except Exception as e:
        logger.error(f"[API::GALAT] Workflow error: {e}")
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/generate")
async def generate_story(request: WorkflowRequest):
    """
    Generate story with full workflow.
    Returns SSE stream with [AGENT::ACTION] events.
    """
    return StreamingResponse(
        generate_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


async def generate_single_agent_sse_stream(request: WorkflowRequest) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for Single Agent workflow (ablation study condition).

    Architecture: research (LightRAG only) -> writer_text (one-shot) -> finalize
    No planner, no critic revision loop, no parallel dispatch.
    Traces tagged as 'SingleAgentWorkflow' in Langfuse for comparison.
    """
    if not WORKFLOW_AVAILABLE:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': 'Workflow not available'})}\n\n"
        return

    job_id = f"single_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    yield f"event: WORKFLOW::MULAI\ndata: {json.dumps({'job_id': job_id, 'mode': 'single_agent', 'message': 'Memulai pembuatan cerita (Single Agent)...'})}\n\n"

    try:
        workflow = _get_single_agent_workflow()

        initial_state = {
            "user_message": request.prompt,
            "theme": request.prompt,
            "target_age": request.target_age or "",
            "language": request.language,
            "story_length": request.story_length or StoryConfig.DEFAULT_STORY_LENGTH,
            "learning_objectives": "",
            "narrative_style": "campuran",
            "active_writers": ["text"],
            "current_stage": "research",
            "messages": [],
            "revision_count": 0,
            "quality_score": 0.0,
            "session_id": job_id,
            "total_tokens": 0,
            "workflow_mode": "single_agent",
        }

        final_state = {}
        langfuse = get_langfuse()
        trace_wrapper = None

        try:
            config = {"run_name": "SingleAgentWorkflow"}
            if langfuse and langfuse.enabled:
                trace_wrapper = langfuse.trace(
                    name="SingleAgentWorkflow",
                    session_id=job_id,
                    user_id=getattr(request, "user_id", "user_v1"),
                    input_data=request.prompt,
                    metadata={
                        "job_id": job_id,
                        "workflow_mode": "single_agent",
                        "target_age": request.target_age,
                        "theme": request.prompt,
                    }
                )
                trace = trace_wrapper.__enter__()
                langfuse.set_parent_trace(trace_wrapper, session_id=job_id)
                initial_state["trace_id"] = trace.trace_id
                logger.info(f"[SINGLE::TRACE] Started single-agent trace: {trace.trace_id}")

                # langfuse langchain CallbackHandler disabled to prevent internal spans like ChatOpenAI/RunnableSequence
                pass

            node_to_tag = {
                "research": "RISET",
                "writer_text": "PENULIS",
                "finalize": "WORKFLOW",
            }

            async for event in workflow.astream_events(initial_state, config=config, version="v2"):
                event_type = event.get("event", "")
                langgraph_node = event.get("metadata", {}).get("langgraph_node", "")

                if event_type == "on_chain_start" and langgraph_node in node_to_tag:
                    tag = node_to_tag[langgraph_node]
                    yield f"event: {tag}::MULAI\ndata: {json.dumps({'agent': langgraph_node, 'status': 'working', 'mode': 'single_agent'})}\n\n"

                elif event_type == "on_chain_end" and langgraph_node in node_to_tag:
                    output = event.get("data", {}).get("output", {})
                    tag = node_to_tag[langgraph_node]

                    if isinstance(output, dict):
                        final_state.update(output)

                    event_data = {"agent": langgraph_node, "status": "done", "mode": "single_agent"}

                    if langgraph_node == "research":
                        notes = output.get("research_notes", "") if isinstance(output, dict) else ""
                        sources = (output.get("research_sources", []) or []) if isinstance(output, dict) else []
                        event_data["chars"] = len(notes)
                        event_data["source_count"] = len(sources)
                        event_data["raw_output"] = {
                            "research_notes": notes,
                            "research_sources": sources,
                        }
                        yield f"event: RISET::MENEMUKAN_INFORMASI\ndata: {json.dumps(event_data)}\n\n"

                    elif langgraph_node == "writer_text":
                        draft = output.get("draft_content", "") if isinstance(output, dict) else ""
                        event_data["chars"] = len(draft)
                        event_data["words"] = len(draft.split())
                        event_data["draft_title"] = output.get("draft_title", "") if isinstance(output, dict) else ""
                        event_data["raw_output"] = {
                            "draft_content": draft,
                            "draft_title": event_data["draft_title"],
                        }
                        yield f"event: PENULIS::SELESAI\ndata: {json.dumps(event_data)}\n\n"

                    elif langgraph_node == "finalize":
                        elapsed = time.time() - start_time
                        final_data = {
                            "job_id": job_id,
                            "mode": "single_agent",
                            "final_story": final_state.get("final_story", ""),
                            "draft_title": final_state.get("draft_title", ""),
                            "quality_score": final_state.get("quality_score", 0),
                            "revision_count": 0,
                            "elapsed_time": round(elapsed, 2),
                        }
                        yield f"event: WORKFLOW::SELESAI\ndata: {json.dumps(final_data)}\n\n"

        finally:
            if trace_wrapper:
                try:
                    if langfuse:
                        langfuse.clear_parent_trace()
                    trace_wrapper.__exit__(None, None, None)
                    logger.info("[SINGLE::TRACE] Single-agent trace closed")
                except Exception as e:
                    logger.error(f"[SINGLE::TRACE] Error closing trace: {e}")

    except Exception as e:
        logger.error(f"[API::GALAT] Single agent workflow error: {e}")
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/generate-single")
async def generate_single_agent_story(request: WorkflowRequest):
    """
    Generate story using Single Agent mode (ablation study condition).

    Condition: LightRAG retrieval + one LLM writer (no planner, no critic loop).
    Used to isolate the contribution of multi-agent orchestration vs RAG alone.
    Returns SSE stream with the same event format as /generate.
    """
    return StreamingResponse(
        generate_single_agent_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def generate_blackboard_sse_stream(request: WorkflowRequest) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for Blackboard architecture (C4 -- ablation study).

    Architecture: Decentralized multi-agent blackboard with bid-driven
    contributions. No central supervisor. Agents self-assess whether they
    have something new to add each round (confidence bidding). The highest
    bidder writes to the shared blackboard, repeating until no agent bids
    above min_confidence or max_rounds is reached.

    Differences from generate (C2):
        - No LightRAG retrieval
        - No planning, no critic revision loop
        - No parallel dispatch
        - Knowledge sources: optimist / skeptic / historian / quantitative
        - Traces tagged as 'BlackboardWorkflow' in Langfuse
    """
    if not BLACKBOARD_AVAILABLE:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': 'Blackboard workflow not available'})}\n\n"
        return

    job_id = f"blackboard_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    yield f"event: WORKFLOW::MULAI\ndata: {json.dumps({'job_id': job_id, 'mode': 'blackboard', 'message': 'Memulai pembuatan cerita (Blackboard)...'})}\n\n"

    try:
        langfuse = get_langfuse() if WORKFLOW_AVAILABLE else None
        trace_wrapper = None
        callbacks = []

        try:
            if langfuse and langfuse.enabled:
                trace_wrapper = langfuse.trace(
                    name="BlackboardWorkflow",
                    session_id=job_id,
                    user_id=getattr(request, "user_id", "user_v1"),
                    input_data=request.prompt,
                    metadata={
                        "job_id": job_id,
                        "workflow_mode": "blackboard",
                        "target_age": request.target_age,
                        "language": request.language,
                        "theme": request.prompt,
                    }
                )
                trace = trace_wrapper.__enter__()
                langfuse.set_parent_trace(trace_wrapper, session_id=job_id)
                logger.info(f"[BLACKBOARD::TRACE] Started blackboard trace: {trace.trace_id}")
                callbacks.append(LangfuseGraphCallbackHandler(langfuse, prefix="blackboard::"))

                # langfuse langchain CallbackHandler disabled to prevent internal spans like ChatOpenAI/RunnableSequence
                pass

            arch = create_blackboard_workflow(callbacks=callbacks)

            yield f"event: BLACKBOARD::MULAI\ndata: {json.dumps({'agent': 'blackboard', 'status': 'working', 'mode': 'blackboard', 'task': request.prompt[:200]})}\n\n"

            # Blackboard.run() is synchronous -- run in threadpool with asyncio.to_thread to propagate contextvars
            result = await asyncio.to_thread(arch.run, request.prompt, callbacks=callbacks)

            elapsed = time.time() - start_time

            # Emit per-contribution trace events
            for contribution in result.trace:
                contrib_data = {
                    "agent": contribution.get("agent", ""),
                    "round": contribution.get("round", 0),
                    "content_preview": contribution.get("content", "")[:300],
                }
                yield f"event: BLACKBOARD::KONTRIBUSI\ndata: {json.dumps(contrib_data)}\n\n"

            final_data = {
                "job_id": job_id,
                "mode": "blackboard",
                "final_story": result.output,
                "draft_title": "",
                "quality_score": 0.0,
                "revision_count": 0,
                "elapsed_time": round(elapsed, 2),
                "metadata": {
                    "total_rounds": result.metadata.get("total_rounds", 0),
                    "agents_who_contributed": result.metadata.get("agents_who_contributed", 0),
                    "agents_available": result.metadata.get("agents_available", 0),
                    "max_rounds": result.metadata.get("max_rounds", 0),
                    "agent_invocation_counts": result.state.get("agent_invocation_counts", {}),
                },
            }
            yield f"event: WORKFLOW::SELESAI\ndata: {json.dumps(final_data)}\n\n"

        finally:
            if trace_wrapper:
                try:
                    if langfuse:
                        langfuse.clear_parent_trace()
                    trace_wrapper.__exit__(None, None, None)
                    logger.info("[BLACKBOARD::TRACE] Blackboard trace closed")
                except Exception as e:
                    logger.error(f"[BLACKBOARD::TRACE] Error closing trace: {e}")

    except Exception as e:
        logger.exception(f"[API::GALAT] Blackboard workflow error: {e}")
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/generate-blackboard")
async def generate_blackboard_story(request: WorkflowRequest):
    """
    Generate story using Blackboard architecture (C4 -- ablation study).

    Architecture: Decentralized multi-agent blackboard with bid-driven
    contributions (optimist / skeptic / historian / quantitative).
    No LightRAG, no planner, no critic loop.

    SSE events emitted:
        WORKFLOW::MULAI           - Job started
        BLACKBOARD::MULAI         - Architecture started, task visible
        BLACKBOARD::KONTRIBUSI    - One per agent contribution (round + preview)
        WORKFLOW::SELESAI         - Final output + round metadata
        WORKFLOW::GALAT           - Error (if any)
    """
    return StreamingResponse(
        generate_blackboard_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def generate_debate_sse_stream(request: WorkflowRequest) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for Debate architecture execution.
    """
    if not DEBATE_AVAILABLE:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': 'Debate workflow not available'})}\n\n"
        return

    job_id = f"debate_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    yield f"event: WORKFLOW::MULAI\ndata: {json.dumps({'job_id': job_id, 'message': 'Memulai Debate workflow...'})}\n\n"

    langfuse = get_langfuse() if WORKFLOW_AVAILABLE else None
    trace_wrapper = None
    callbacks = []

    try:
        if langfuse and langfuse.enabled:
            trace_wrapper = langfuse.trace(
                name="DebateWorkflow",
                session_id=job_id,
                user_id=getattr(request, "user_id", "user_v1"),
                input_data=request.prompt,
                metadata={
                    "job_id": job_id,
                    "workflow_mode": "debate",
                    "target_age": request.target_age,
                    "language": request.language,
                    "theme": request.prompt,
                    "llm_model": request.model or "(env default)",
                }
            )
            trace = trace_wrapper.__enter__()
            langfuse.set_parent_trace(trace_wrapper, session_id=job_id)
            logger.info(f"[DEBATE::TRACE] Started debate trace: {trace.trace_id}")
            callbacks.append(LangfuseGraphCallbackHandler(langfuse, prefix="debate::"))

        # Use custom model instance if specified, otherwise reuse singleton
        if request.model:
            arch = create_debate_workflow(model_name=request.model)
        else:
            arch = _get_debate_workflow()

        yield f"event: DEBATE::MULAI\ndata: {json.dumps({'agent': 'debate', 'status': 'working', 'mode': 'debate', 'task': request.prompt[:200]})}\n\n"

        result = await asyncio.to_thread(arch.run, request.prompt, callbacks=callbacks)

        elapsed = time.time() - start_time

        for round_data in result.trace:
            round_event = {
                "round": round_data.get("round", 0),
                "n_agents": len(round_data.get("agents", [])),
                "answers_preview": [
                    a.get("answer", "")[:100] for a in round_data.get("agents", [])
                ],
            }
            yield f"event: DEBATE::RONDE\ndata: {json.dumps(round_event)}\n\n"

        final_data = {
            "job_id": job_id,
            "mode": "debate",
            "final_story": result.output,
            "draft_title": "",
            "quality_score": 0.0,
            "revision_count": 0,
            "elapsed_time": round(elapsed, 2),
            "metadata": {
                "convergence": result.metadata.get("convergence", False),
                "final_tally": result.metadata.get("final_tally", {}),
                "round_unique_answer_count": result.metadata.get("round_unique_answer_count", []),
                "n_agents": result.metadata.get("n_agents", 3),
                "n_rounds": result.metadata.get("n_rounds", 2),
            },
        }
        yield f"event: WORKFLOW::SELESAI\ndata: {json.dumps(final_data)}\n\n"

    finally:
        if trace_wrapper:
            try:
                if langfuse:
                    langfuse.clear_parent_trace()
                trace_wrapper.__exit__(None, None, None)
                logger.info("[DEBATE::TRACE] Debate trace closed")
            except Exception as e:
                logger.error(f"[DEBATE::TRACE] Error closing trace: {e}")

    # Note: exception block is outside finally to still emit WORKFLOW::GALAT
    # The try/finally above handles trace cleanup regardless of outcome.


@router.post("/generate-debate")
async def generate_debate_story(request: WorkflowRequest):
    """
    Generate story using Debate architecture (Du et al., 2023).

    Architecture: 3 agents (rigorous / skeptical / pragmatic) debate over
    2 rounds and majority-vote to the final answer. No external retrieval.

    SSE events emitted:
        WORKFLOW::MULAI     - Job started
        DEBATE::MULAI       - Architecture started, task visible
        DEBATE::RONDE       - One per round (n_agents, answer previews)
        WORKFLOW::SELESAI   - Final output + convergence metadata
        WORKFLOW::GALAT     - Error (if any)
    """
    return StreamingResponse(
        generate_debate_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def generate_storm_sse_stream(request: WorkflowRequest) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream for STORM architecture execution.
    """
    if not STORM_AVAILABLE:
        yield f"event: WORKFLOW::GALAT\ndata: {json.dumps({'error': 'STORM workflow not available'})}\n\n"
        return

    job_id = f"storm_{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    yield f"event: WORKFLOW::MULAI\ndata: {json.dumps({'job_id': job_id, 'message': 'Memulai STORM workflow...'})}\n\n"

    langfuse = get_langfuse() if WORKFLOW_AVAILABLE else None
    trace_wrapper = None
    callbacks = []

    try:
        if langfuse and langfuse.enabled:
            trace_wrapper = langfuse.trace(
                name="StormWorkflow",
                session_id=job_id,
                user_id=getattr(request, "user_id", "user_v1"),
                input_data=request.prompt,
                metadata={
                    "job_id": job_id,
                    "workflow_mode": "storm",
                    "target_age": request.target_age,
                    "language": request.language,
                    "theme": request.prompt,
                    "llm_model": request.model or "(env default)",
                }
            )
            trace = trace_wrapper.__enter__()
            langfuse.set_parent_trace(trace_wrapper, session_id=job_id)
            logger.info(f"[STORM::TRACE] Started storm trace: {trace.trace_id}")
            callbacks.append(LangfuseGraphCallbackHandler(langfuse, prefix="storm::"))

        # Use custom model instance if specified, otherwise reuse singleton
        if request.model:
            arch = create_storm_workflow(language=request.language, model_name=request.model)
        else:
            arch = _get_storm_workflow(language=request.language)

        yield f"event: STORM::MULAI\ndata: {json.dumps({'agent': 'storm', 'status': 'working', 'mode': 'storm', 'task': request.prompt[:200]})}\n\n"

        result = await asyncio.to_thread(arch.run, request.prompt, callbacks=callbacks)

        elapsed = time.time() - start_time

        # Emit intermediate metadata events
        perspectives = result.metadata.get("perspectives", [])
        if perspectives:
            yield f"event: STORM::PERSPEKTIF\ndata: {json.dumps({'perspectives': perspectives})}\n\n"

        outline = result.metadata.get("outline", [])
        if outline:
            yield f"event: STORM::OUTLINE\ndata: {json.dumps({'outline': outline, 'n_sections': len(outline)})}\n\n"

        final_data = {
            "job_id": job_id,
            "mode": "storm",
            "final_story": result.output,
            "draft_title": "",
            "quality_score": 0.0,
            "revision_count": 0,
            "elapsed_time": round(elapsed, 2),
            "metadata": {
                "n_perspectives": result.metadata.get("n_perspectives", 0),
                "n_questions": result.metadata.get("n_questions", 0),
                "n_sections": result.metadata.get("n_sections", 0),
                "article_chars": result.metadata.get("article_chars", 0),
                "perspectives": perspectives,
                "outline": outline,
            },
        }
        yield f"event: WORKFLOW::SELESAI\ndata: {json.dumps(final_data)}\n\n"

    finally:
        if trace_wrapper:
            try:
                if langfuse:
                    langfuse.clear_parent_trace()
                trace_wrapper.__exit__(None, None, None)
                logger.info("[STORM::TRACE] Storm trace closed")
            except Exception as e:
                logger.error(f"[STORM::TRACE] Error closing trace: {e}")


@router.post("/generate-storm")
async def generate_storm_story(request: WorkflowRequest):
    """
    Generate article using STORM architecture (Shao et al., 2024).

    Architecture: Multi-perspective research pipeline -- discovers perspectives,
    simulates Q&A conversations grounded on web search, creates outline, then
    writes a full-length article section by section.

    SSE events emitted:
        WORKFLOW::MULAI       - Job started
        STORM::MULAI          - Pipeline started, task visible
        STORM::PERSPEKTIF     - Perspectives discovered
        STORM::OUTLINE        - Article outline created
        WORKFLOW::SELESAI     - Final article + pipeline metadata
        WORKFLOW::GALAT       - Error (if any)
    """
    return StreamingResponse(
        generate_storm_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
