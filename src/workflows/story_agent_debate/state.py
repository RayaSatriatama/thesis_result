"""
State schema for Debate architecture wrapper.

Mirrors the library's internal Debate state and adds API-compatibility fields
(workflow_mode, language, session_id, trace_id) that the router relies on for
Langfuse tracing and response metadata.
These extra fields are never passed into the library -- only used at the
API boundary.
"""

from typing import Annotated, Any, Dict, List
import operator

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

from typing import TypedDict


class DebateWrapperState(TypedDict, total=False):
    """
    State for the Debate architecture wrapper.

    Library fields (Debate internal state):
        task          - The input task string passed to arch.run()
        rounds        - Per-round agent responses (answer + critique_of_others)
        final_answer  - Majority-voted answer from the last round

    API wrapper fields (not passed to library):
        workflow_mode - Always "debate"; used for Langfuse metadata
        language      - "Indonesian" | "English"; included in task prompt
        theme         - Raw topic from user request
        session_id    - Job ID for Langfuse session grouping
        trace_id      - Langfuse trace ID for distributed propagation
    """

    # --- Library Debate fields ---
    task: str
    rounds: List[List[Dict[str, Any]]]
    final_answer: str
    convergence: bool
    final_tally: Dict[str, int]
    round_unique_answer_count: List[int]

    # --- API wrapper fields ---
    workflow_mode: str
    language: str
    theme: str
    session_id: str
    trace_id: str
