"""
State schema for STORM architecture wrapper.

Mirrors the library's internal STORM state and adds API-compatibility fields
(workflow_mode, language, session_id, trace_id) that the router relies on for
Langfuse tracing and response metadata.
These extra fields are never passed into the library -- only used at the
API boundary.
"""

from typing import Any, Dict, List

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

from typing import TypedDict


class StormWrapperState(TypedDict, total=False):
    """
    State for the STORM architecture wrapper.

    Library fields (STORM internal state -- from graph.invoke final_state):
        topic         - The input topic string passed to arch.run()
        perspectives  - Discovered perspectives (list[str])
        questions     - Generated questions per perspective (list[dict])
        answers       - Answers to questions via web search (list[dict])
        outline       - Refined article outline (list[dict])
        final_answer  - The full-length generated article

    API wrapper fields (not passed to library):
        workflow_mode - Always "storm"; used for Langfuse metadata
        language      - "Indonesian" | "English"; included in task prompt
        theme         - Raw topic from user request
        session_id    - Job ID for Langfuse session grouping
        trace_id      - Langfuse trace ID for distributed propagation
    """

    # --- Library STORM fields ---
    topic: str
    perspectives: List[str]
    questions: List[Dict[str, Any]]
    answers: List[Dict[str, Any]]
    outline: List[Dict[str, Any]]
    final_answer: str

    # --- API wrapper fields ---
    workflow_mode: str
    language: str
    theme: str
    session_id: str
    trace_id: str
