"""
Langfuse Trace and Span Wrapper Classes.

Context managers for Langfuse traces and spans using SDK 3.x API.
"""

from typing import Dict, List, Optional, Any

import time

from loguru import logger

from ._constants import Langfuse


# =============================================================================
# Trace Wrapper (Context Manager using start_as_current_span)
# =============================================================================

class TraceWrapper:
    """
    Context manager for Langfuse traces using SDK 3.x API.
    Uses start_as_current_span() for proper trace management.

    Based on SDK docs, span.trace_id is available after entering context.
    Use span.score_trace() for trace-level scores.
    """

    def __init__(
        self,
        client: Optional[Langfuse],
        enabled: bool,
        name: str,
        user_id: str = None,
        session_id: str = None,
        input_data: Any = None,
        metadata: Dict[str, Any] = None,
        tags: List[str] = None
    ):
        self._client = client
        self.enabled = enabled
        self.name = name
        self.user_id = user_id
        self.session_id = session_id
        self.input_data = input_data
        self.metadata = metadata or {}
        self.tags = tags or []
        self._trace_id = None
        self._span_context = None
        self._start_time = None

    def __enter__(self) -> "TraceWrapper":
        """Start the trace using start_as_current_span."""
        self._start_time = time.time()

        if self.enabled and self._client:
            try:
                # Use start_as_current_span API - it returns a context manager
                self._span_context = self._client.start_as_current_span(
                    name=self.name,
                    input=self.input_data,
                    metadata={
                        **self.metadata,
                        "session_id": self.session_id,
                        "user_id": self.user_id,
                        "tags": self.tags
                    }
                )
                # Enter the span context
                self._span = self._span_context.__enter__()
                # trace_id is available on the returned span object
                self._trace_id = getattr(self._span, 'trace_id', None)
            except Exception as e:
                logger.warning(f"Failed to create trace: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the trace."""
        if self._span_context:
            try:
                self._span_context.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"Failed to exit trace context: {e}")

        # Always try to flush after exiting trace
        if self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.warning(f"Failed to flush after trace exit: {e}")

        return False

    @property
    def trace_id(self) -> Optional[str]:
        """Get the trace ID."""
        return self._trace_id

    def span(
        self,
        name: str,
        metadata: Dict[str, Any] = None,
        input: Any = None
    ) -> "SpanWrapper":
        """Create a span within this trace."""
        return SpanWrapper(
            client=self._client,
            enabled=self.enabled,
            name=name,
            metadata=metadata,
            input=input
        )

    def score(self, name: str, value: float, comment: str = None):
        """Add a score to this trace using span.score_trace()."""
        if not self.enabled or not hasattr(self, '_span') or not self._span:
            return

        try:
            # Use score_trace on the span for trace-level scores
            self._span.score_trace(
                name=name,
                value=value,
                data_type="NUMERIC",
                comment=comment
            )
        except Exception as e:
            # Fallback to create_score if score_trace not available
            if self._trace_id and self._client:
                try:
                    self._client.create_score(
                        trace_id=self._trace_id,
                        name=name,
                        value=value,
                        comment=comment,
                        data_type="NUMERIC"
                    )
                except Exception:
                    pass

    def update(self, output: Any = None, metadata: Dict[str, Any] = None):
        """Update trace metadata."""
        if hasattr(self, '_span') and self._span:
            try:
                if output or metadata:
                    self._span.update_trace(
                        user_id=self.user_id,
                        session_id=self.session_id,
                        metadata=metadata,
                        tags=self.tags
                    )
                if output:
                    self._span.update(output=output)
            except Exception:
                pass


# =============================================================================
# Span Wrapper (Nested Spans)
# =============================================================================

class SpanWrapper:
    """Context manager for Langfuse spans."""

    def __init__(
        self,
        client,
        enabled: bool,
        name: str,
        metadata: Dict[str, Any] = None,
        input: Any = None
    ):
        self._client = client
        self.enabled = enabled
        self.name = name
        self.metadata = metadata or {}
        self.input = input
        self._span = None

    def __enter__(self) -> "SpanWrapper":
        """Start the span."""
        if self.enabled and self._client:
            try:
                self._span = self._client.start_as_current_span(
                    name=self.name,
                    input=self.input,
                    metadata=self.metadata
                )
                self._span.__enter__()
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the span."""
        if self._span:
            try:
                self._span.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
        return False

    def update(self, output: Any = None, metadata: Dict[str, Any] = None):
        """Update span output."""
        if self._span and self._client:
            try:
                self._client.update_current_span(
                    output=output,
                    metadata=metadata
                )
            except Exception:
                pass
