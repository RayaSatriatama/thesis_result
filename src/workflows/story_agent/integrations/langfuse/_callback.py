"""
LangChain/LangGraph Callback Handler for Langfuse.

Custom callback handler that logs high-level LangGraph nodes to Langfuse
without the noise or event loop issues of the default LangChain handler.
"""

from typing import Dict, Any, TYPE_CHECKING

from langchain_core.callbacks import BaseCallbackHandler

if TYPE_CHECKING:
    from ._client import LangfuseClient


class LangfuseGraphCallbackHandler(BaseCallbackHandler):
    """
    Custom LangChain callback handler for LangGraph execution that logs
    high-level nodes to Langfuse without the noise or event loop issues
    of the default Langchain callback handler.
    """
    def __init__(self, langfuse_client: "LangfuseClient", prefix: str = ""):
        self.lf = langfuse_client
        self.prefix = prefix
        self.active_spans = {}  # run_id -> span_id

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], *, run_id: str, parent_run_id: str = None, tags: list = None, metadata: Dict[str, Any] = None, **kwargs: Any
    ):
        node_name = (metadata or {}).get("langgraph_node")
        # Only log actual graph nodes, ignore internal LangGraph __start__ etc.
        if node_name and not node_name.startswith("__"):
            span_name = f"{self.prefix}{node_name}"
            # Extract only standard input formats to avoid serializing massive objects
            clean_input = inputs
            if isinstance(inputs, dict):
                clean_input = {k: v for k, v in inputs.items() if k != "messages"} # Optional: filter large message arrays
            
            span_id = self.lf.start_span(name=span_name, input_data=clean_input, metadata=metadata)
            if span_id:
                self.active_spans[str(run_id)] = span_id

    def on_chain_end(
        self, outputs: Dict[str, Any], *, run_id: str, parent_run_id: str = None, **kwargs: Any
    ):
        span_id = self.active_spans.pop(str(run_id), None)
        if span_id:
            # Avoid serializing massive objects
            clean_output = outputs
            if isinstance(outputs, dict):
                clean_output = {k: v for k, v in outputs.items() if k != "messages"}
            self.lf.end_span(span_id=span_id, output_data=clean_output)

    def on_chain_error(
        self, error: BaseException, *, run_id: str, parent_run_id: str = None, **kwargs: Any
    ):
        span_id = self.active_spans.pop(str(run_id), None)
        if span_id:
            self.lf.end_span(span_id=span_id, output_data={"error": str(error)})
