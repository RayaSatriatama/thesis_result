"""
Trace Extractor -- Extract output and context data from Langfuse traces.

Provides per-workflow extraction functions that normalize trace data
into a common schema consumable by FaithfulnessEvaluator.

Supported workflows:
  - STORM  (StormWorkflow)
  - Multi-agent / Story Agent (StoryGenerationWorkflow)
  - Debate (DebateWorkflow)

Usage:
    from scripts.trace_extractor import extract_trace_data

    data = extract_trace_data(trace)
    # data["output"]   -> str (final text)
    # data["contexts"] -> list[str] (reference contexts)
    # data["workflow"]  -> str (workflow name)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# Mapping from Langfuse trace name to internal workflow key.
TRACE_NAME_TO_WORKFLOW = {
    "StormWorkflow": "storm",
    "StoryGenerationWorkflow": "multi_agent",
    "SingleAgentWorkflow": "single_agent",
    "DebateWorkflow": "debate",
    "BlackboardWorkflow": "blackboard",
}


@dataclass
class TraceData:
    """Normalized data extracted from a single Langfuse trace."""

    trace_id: str
    workflow: str
    output: str
    contexts: List[str] = field(default_factory=list)
    prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    has_contexts: bool = False


def extract_storm_data(trace: Any) -> TraceData:
    """
    Extract output and contexts from a STORM trace.

    STORM output : trace.output["final_story"] or trace.output (str)
    STORM contexts: trace.metadata["answers"] -> list of {"question": ..., "answer": ...}
                    Each answer is treated as a reference context.
    """
    trace_id = _get_trace_id(trace)
    output_raw = _get_output(trace)
    meta = _get_metadata(trace)

    # Extract contexts from Q&A answers in metadata
    contexts = []
    answers = meta.get("answers", [])
    if isinstance(answers, list):
        for entry in answers:
            if isinstance(entry, dict):
                ans_text = entry.get("answer", "")
                if ans_text and isinstance(ans_text, str):
                    contexts.append(ans_text)

    prompt = meta.get("theme", "") or _get_input(trace)

    return TraceData(
        trace_id=trace_id,
        workflow="storm",
        output=output_raw,
        contexts=contexts,
        prompt=prompt,
        metadata=meta,
        has_contexts=bool(contexts),
    )


def extract_multiagent_data(trace: Any) -> TraceData:
    """
    Extract output and contexts from a Multi-agent (story agent) trace.

    Output  : trace.output["final_story"] or trace.output (str)
    Contexts: from metadata or nested observations -- research_notes + research_sources.
    """
    trace_id = _get_trace_id(trace)
    output_raw = _get_output(trace)
    meta = _get_metadata(trace)

    # Try to get research data from trace output (merged state)
    contexts = []
    output_dict = _get_output_dict(trace)

    # Research notes as primary context
    research_notes = output_dict.get("research_notes", "")
    if research_notes and isinstance(research_notes, str):
        contexts.append(research_notes)

    # Research sources as additional context
    research_sources = output_dict.get("research_sources", [])
    if isinstance(research_sources, list):
        for src in research_sources:
            if isinstance(src, dict):
                text = src.get("text", "") or src.get("content", "")
                if text:
                    contexts.append(text)
            elif isinstance(src, str) and src:
                contexts.append(src)

    prompt = meta.get("theme", "") or _get_input(trace)

    return TraceData(
        trace_id=trace_id,
        workflow="multi_agent",
        output=output_raw,
        contexts=contexts,
        prompt=prompt,
        metadata=meta,
        has_contexts=bool(contexts),
    )


def extract_debate_data(trace: Any) -> TraceData:
    """
    Extract output from a Debate trace.

    Debate has no retrieval -- contexts will be empty.
    Caller should provide ground truth contexts externally if needed.
    """
    trace_id = _get_trace_id(trace)
    output_raw = _get_output(trace)
    meta = _get_metadata(trace)

    prompt = meta.get("theme", "") or _get_input(trace)

    return TraceData(
        trace_id=trace_id,
        workflow="debate",
        output=output_raw,
        contexts=[],
        prompt=prompt,
        metadata=meta,
        has_contexts=False,
    )


def extract_trace_data(trace: Any) -> TraceData:
    """
    Auto-detect workflow type from trace name and extract data accordingly.

    Falls back to generic extraction if workflow type is unrecognized.
    """
    trace_name = _get_trace_name(trace)
    workflow = TRACE_NAME_TO_WORKFLOW.get(trace_name, "unknown")

    if workflow == "storm":
        return extract_storm_data(trace)
    elif workflow in ("multi_agent", "single_agent"):
        return extract_multiagent_data(trace)
    elif workflow == "debate":
        return extract_debate_data(trace)
    elif workflow == "blackboard":
        # Blackboard has no retrieval, same as debate
        return extract_debate_data(trace)
    else:
        logger.warning(
            f"[EXTRACTOR] Unknown trace name '{trace_name}', "
            "using generic extraction."
        )
        return _extract_generic(trace)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_trace_id(trace: Any) -> str:
    """Extract trace ID from various trace object shapes."""
    if isinstance(trace, dict):
        return str(trace.get("id", "") or trace.get("trace_id", ""))
    return str(getattr(trace, "id", "") or getattr(trace, "trace_id", ""))


def _get_trace_name(trace: Any) -> str:
    """Extract trace name from various trace object shapes."""
    if isinstance(trace, dict):
        return str(trace.get("name", ""))
    return str(getattr(trace, "name", ""))


def _get_output(trace: Any) -> str:
    """Extract output text from trace, handling dict or string output."""
    raw_output = None
    if isinstance(trace, dict):
        raw_output = trace.get("output")
    else:
        raw_output = getattr(trace, "output", None)

    if raw_output is None:
        return ""

    if isinstance(raw_output, str):
        return raw_output

    if isinstance(raw_output, dict):
        # Try common keys
        for key in ("final_story", "final_answer", "output", "text", "content"):
            val = raw_output.get(key)
            if val and isinstance(val, str):
                return val
        # Fallback: stringify
        return str(raw_output)

    return str(raw_output)


def _get_output_dict(trace: Any) -> dict:
    """Get output as dict (for extracting sub-fields like research_notes)."""
    raw_output = None
    if isinstance(trace, dict):
        raw_output = trace.get("output")
    else:
        raw_output = getattr(trace, "output", None)

    if isinstance(raw_output, dict):
        return raw_output
    return {}


def _get_input(trace: Any) -> str:
    """Extract input/prompt from trace."""
    raw_input = None
    if isinstance(trace, dict):
        raw_input = trace.get("input")
    else:
        raw_input = getattr(trace, "input", None)

    if raw_input is None:
        return ""
    if isinstance(raw_input, str):
        return raw_input
    if isinstance(raw_input, dict):
        return str(raw_input.get("prompt", "") or raw_input.get("theme", ""))
    return str(raw_input)


def _get_metadata(trace: Any) -> dict:
    """Extract metadata dict from trace."""
    if isinstance(trace, dict):
        meta = trace.get("metadata")
    else:
        meta = getattr(trace, "metadata", None)

    if isinstance(meta, dict):
        return meta
    return {}


def _extract_generic(trace: Any) -> TraceData:
    """Generic fallback extraction."""
    return TraceData(
        trace_id=_get_trace_id(trace),
        workflow="unknown",
        output=_get_output(trace),
        contexts=[],
        prompt=_get_input(trace),
        metadata=_get_metadata(trace),
        has_contexts=False,
    )
