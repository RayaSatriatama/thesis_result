"""
State schema for Blackboard architecture wrapper.

Mirrors the library's BlackboardState and adds API-compatibility fields
(workflow_mode, language, session_id, trace_id) that the router relies on.
These extra fields are never passed into the library -- only used at the
API boundary for Langfuse tracing and response metadata.
"""

from typing import Annotated, Any, Dict, List
import operator

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

from typing import TypedDict


class BlackboardWrapperState(TypedDict, total=False):
    """
    State for the Blackboard architecture wrapper.

    Library fields (BlackboardState):
        task            - The input task string passed to arch.run()
        blackboard      - Accumulated contributions (append-only via operator.add)
        round           - Current bidding round number
        max_rounds      - Maximum allowed rounds
        next_agent      - Name of the winning bidder for this round
        last_bids       - Dict of all bids from the current round
        final_synthesis - Final synthesized output from the blackboard

    API wrapper fields (not passed to library):
        workflow_mode   - Always "blackboard"; used for Langfuse metadata
        language        - "Indonesian" | "English"; passed in task prompt
        theme           - Raw topic from user request
        session_id      - Job ID for Langfuse session grouping
        trace_id        - Langfuse trace ID for distributed propagation
    """

    # --- Library BlackboardState fields ---
    task: str
    blackboard: Annotated[List[Dict[str, Any]], operator.add]
    round: int
    max_rounds: int
    next_agent: str
    last_bids: Dict[str, Dict[str, Any]]
    final_synthesis: str

    # --- API wrapper fields ---
    workflow_mode: str
    language: str
    theme: str
    session_id: str
    trace_id: str
