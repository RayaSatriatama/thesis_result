"""
Langfuse Client - Observability and Tracing for Story Agent
Klien Langfuse untuk Observability dan Tracing

Based on Langfuse Python SDK 3.x
Docs: https://langfuse.com/docs/sdk/python

Token Tracking via OpenTelemetry (provider-agnostic):
  - Google Vertex AI  : openinference-instrumentation-vertexai
  - OpenAI-compatible : openinference-instrumentation-openai
    (covers DeepSeek, GLM, Ollama, OpenAI)
https://langfuse.com/docs/integrations/google-vertex-ai
"""

from typing import Dict, List, Optional, Any

import re
import time
from contextlib import contextmanager

from loguru import logger

from settings import ObservabilityConfig

from ._constants import LANGFUSE_AVAILABLE, Langfuse
from ._otel_setup import setup_otel_instrumentation
from ._ingestion import IngestionMixin
from ._faithfulness import FaithfulnessMixin
from ._wrappers import TraceWrapper, SpanWrapper


# =============================================================================
# Langfuse Client Wrapper (Langfuse 3.x API)
# =============================================================================

class LangfuseClient(IngestionMixin, FaithfulnessMixin):
    """
    Wrapper for Langfuse observability and tracing using SDK 3.x API.

    Uses start_as_current_span() API for context-managed tracing.

    Parent Trace Management:
    - Use set_parent_trace() to establish a parent trace for all subsequent spans
    - All start_span() calls will create child spans under the parent trace
    - Use clear_parent_trace() when workflow completes
    """

    def __init__(self):
        """Initialize Langfuse client with settings from config."""
        self.enabled = ObservabilityConfig.LANGFUSE_ENABLED and LANGFUSE_AVAILABLE
        self._client: Optional[Langfuse] = None
        self._current_trace_id: Optional[str] = None
        self._current_span = None
        self._spans: Dict[str, Any] = {}
        self._otel_initialized = False
        self._callback_handler = None

        # Parent trace management for nested spans across agents
        self._parent_trace: Optional[Any] = None  # The TraceWrapper from trace()
        self._parent_span: Optional[Any] = None   # Current active span for nesting
        self._span_stack: List[Any] = []          # Stack of spans for proper nesting
        self._parent_trace_id: Optional[str] = None
        self._parent_session_id: Optional[str] = None

        # When set, start_span / log_generation pass trace_context so spans attach to an
        # existing Langfuse trace (faithfulness replay without regenerating the story).
        self._faithfulness_replay_trace_context: Optional[Dict[str, str]] = None
        # When recreating fables_faithfulness under ragas_evaluation: real 16-hex observation id
        # so ingestion generation-create nests under the new span (not under ragas).
        self._faithfulness_generation_parent_id: Optional[str] = None
        self._faithfulness_fables_ingestion_start_time: Optional[str] = None

        if self.enabled:
            try:
                self._client = Langfuse(
                    secret_key=ObservabilityConfig.LANGFUSE_SECRET_KEY,
                    public_key=ObservabilityConfig.LANGFUSE_PUBLIC_KEY,
                    host=ObservabilityConfig.LANGFUSE_HOST
                )
                logger.success(f"[LANGFUSE::INISIALISASI] Initialized (project: {ObservabilityConfig.LANGFUSE_PROJECT_NAME})")

                # Initialize OpenTelemetry (provider-agnostic)
                self._otel_initialized = setup_otel_instrumentation()

            except Exception as e:
                logger.warning(f"Langfuse initialization failed: {e}")
                self.enabled = False
        else:
            if not LANGFUSE_AVAILABLE:
                logger.warning("Langfuse not installed. Run: pip install langfuse")
            else:
                logger.info("Langfuse disabled in settings")

    @property
    def client(self) -> Optional[Langfuse]:
        """Get the underlying Langfuse client."""
        return self._client

    @property
    def callback_handler(self):
        """
        Get the LangChain CallbackHandler for automatic token tracking.

        NOTE: Currently disabled due to event loop conflicts with async frameworks.
        Always returns None.
        """
        return None

    def get_callback_config(self, session_id: str = None, user_id: str = None, tags: List[str] = None) -> dict:
        """
        Get a LangChain config dict with Langfuse callback handler.

        NOTE: Currently returns empty dict due to event loop conflicts with
        async frameworks. Token tracking must be done manually
        or via OpenTelemetry integration.

        See: https://langfuse.com/docs/integrations/google-vertex-ai

        Args:
            session_id: Optional session ID (not used - callbacks disabled)
            user_id: Optional user ID (not used - callbacks disabled)
            tags: Optional tags (not used - callbacks disabled)

        Returns:
            Empty dict (callbacks disabled)
        """
        return {}

    # =========================================================================
    # ID normalization (shared by IngestionMixin and FaithfulnessMixin via self)
    # =========================================================================

    @staticmethod
    def _normalize_trace_id(raw: Optional[str]) -> str:
        if not raw:
            return ""
        s = str(raw).strip().replace("-", "").lower()
        if len(s) == 32 and re.fullmatch(r"[0-9a-f]{32}", s):
            return s
        return str(raw).strip()

    @staticmethod
    def _normalize_span_id(raw: Optional[str]) -> str:
        if not raw:
            return ""
        s = str(raw).strip().replace("-", "").lower()
        if len(s) == 16 and re.fullmatch(r"[0-9a-f]{16}", s):
            return s
        return str(raw).strip()

    # =========================================================================
    # Parent Trace Management (for unified tracing across agents)
    # =========================================================================

    def set_parent_trace(self, trace_wrapper: "TraceWrapper", session_id: str = None):
        """
        Set the parent trace for all subsequent spans.

        Call this before running a workflow to ensure all agent spans
        are nested under a single parent trace.

        Args:
            trace_wrapper: The TraceWrapper object from trace() call
            session_id: Optional session ID for grouping
        """
        self._parent_trace = trace_wrapper
        # Store the actual Langfuse span object for creating nested spans
        self._parent_span = trace_wrapper._span if trace_wrapper and hasattr(trace_wrapper, '_span') else None
        self._parent_trace_id = trace_wrapper.trace_id if trace_wrapper else None
        self._parent_session_id = session_id
        if self._parent_trace_id:
            logger.debug(f"[LANGFUSE::JEJAK] Parent trace set: {self._parent_trace_id[:16]}...")

    def clear_parent_trace(self):
        """
        Clear the parent trace after workflow completes.
        """
        self._parent_trace = None
        self._parent_span = None
        self._parent_trace_id = None
        self._parent_session_id = None

    def get_parent_trace_id(self) -> Optional[str]:
        """Get the current parent trace ID."""
        return self._parent_trace_id

    def has_parent_trace(self) -> bool:
        """Check if a parent trace is active."""
        return self._parent_span is not None

    # =========================================================================
    # Context Manager API (recommended)
    # =========================================================================

    def trace(
        self,
        name: str,
        user_id: str = None,
        session_id: str = None,
        input_data: Any = None,
        metadata: Dict[str, Any] = None,
        tags: List[str] = None
    ) -> "TraceWrapper":
        """
        Create a new trace as context manager.

        Args:
            name: Trace name
            user_id: Optional user identifier
            session_id: Optional session identifier
            input_data: Input data for the trace
            metadata: Additional metadata
            tags: Tags for filtering

        Returns:
            TraceWrapper context manager
        """
        return TraceWrapper(
            client=self._client,
            enabled=self.enabled,
            name=name,
            user_id=user_id,
            session_id=session_id,
            input_data=input_data,
            metadata=metadata,
            tags=tags
        )

    # =========================================================================
    # Imperative API (for agents)
    # =========================================================================

    def start_trace(
        self,
        session_id: str,
        name: str,
        input_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
        user_id: str = None
    ) -> Optional[str]:
        """
        Start a new trace imperatively.

        Returns:
            trace_id if successful, None otherwise
        """
        if not self.enabled or not self._client:
            return None

        try:
            # Use start_as_current_span which returns a context manager
            self._current_span = self._client.start_as_current_span(
                name=name,
                input=input_data,
                metadata={
                    **(metadata or {}),
                    "session_id": session_id,
                    "user_id": user_id
                }
            )
            # Enter the context
            span = self._current_span.__enter__()
            # Get trace_id from the span object
            self._current_trace_id = getattr(span, 'trace_id', None)
            self._active_span = span
            return self._current_trace_id
        except Exception as e:
            logger.warning(f"Failed to start trace: {e}")
            return None

    def end_trace(
        self,
        trace_id: str = None,
        output_data: Dict[str, Any] = None
    ):
        """End current trace."""
        if not self.enabled or not self._current_span:
            return

        try:
            self._current_span.__exit__(None, None, None)
            self._current_span = None
            self._current_trace_id = None
        except Exception:
            pass

    def start_span(
        self,
        name: str,
        input_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Start a span within the current trace or parent trace.

        Creates spans using client.start_as_current_span() which manages
        nesting automatically via the current context.

        Returns:
            span_id if successful, None otherwise
        """
        if not self.enabled or not self._client:
            return None

        try:
            # Add parent trace info to metadata
            enhanced_metadata = metadata or {}
            if self._parent_trace_id:
                enhanced_metadata["parent_trace_id"] = self._parent_trace_id
            if self._parent_session_id:
                enhanced_metadata["session_id"] = self._parent_session_id

            # Always use client.start_as_current_span() - it manages parent context automatically
            # The SDK maintains a context stack, so nested calls automatically become children
            span_kwargs: Dict[str, Any] = {
                "name": name,
                "input": input_data,
                "metadata": enhanced_metadata,
            }
            if self._faithfulness_replay_trace_context:
                span_kwargs["trace_context"] = self._faithfulness_replay_trace_context

            span_context = self._client.start_as_current_span(**span_kwargs)

            span = span_context.__enter__()
            span_id = str(id(span_context))
            self._spans[span_id] = span_context

            # Push to span stack for tracking
            self._span_stack.append(span_context)

            return span_id
        except Exception as e:
            logger.warning(f"Failed to start span: {e}")
            return None

    def end_span(
        self,
        span_id: str,
        output_data: Dict[str, Any] = None
    ):
        """End a span and set output data."""
        if not self.enabled or span_id not in self._spans:
            return

        try:
            span_context = self._spans.pop(span_id, None)
            if span_context:
                # Update output BEFORE exiting the span context
                if output_data and self._client:
                    try:
                        self._client.update_current_span(output=output_data)
                    except Exception as e:
                        logger.warning(f"Failed to update span output: {e}")
                span_context.__exit__(None, None, None)

                # Pop from span stack
                if self._span_stack and span_context in self._span_stack:
                    self._span_stack.remove(span_context)
        except Exception as e:
            logger.warning(f"Failed to end span: {e}")

    def create_score(
        self,
        name: str,
        value: float,
        trace_id: str = None,
        observation_id: str = None,
        comment: str = None,
        data_type: str = "NUMERIC",
        metadata: Dict[str, Any] = None
    ):
        """
        Create a score for a trace or observation in Langfuse.



        Args:
            name: Score name (e.g., "educational_score", "coherence_score")
            trace_id: Optional trace ID to attach score to (uses parent trace if not provided)
            observation_id: Optional observation ID to attach score to
            comment: Optional comment explaining the score
            data_type: Score data type ("NUMERIC", "BOOLEAN", "CATEGORICAL")
            metadata: Additional metadata to attach
        """
        if not self.enabled or not self._client:
            return

        try:
            # Use parent trace ID if not provided
            if not trace_id and self._parent_trace_id:
                trace_id = self._parent_trace_id

            if not trace_id:
                logger.warning("create_score: No trace_id provided and no parent trace set")
                return

            # Call Langfuse create_score API
            self._client.create_score(
                name=name,
                value=value,
                trace_id=trace_id,
                observation_id=observation_id,
                comment=comment,
                data_type=data_type,
                metadata=metadata or {}
            )
            logger.debug(f"[LANGFUSE::SKOR] Score logged: {name}={value}")
        except Exception as e:
            logger.warning(f"[LANGFUSE::ERROR] Failed to create score: {e}")

    def log_span(
        self,
        name: str,
        input_data: Any = None,
        output_data: Any = None,
        metadata: Dict[str, Any] = None,
        start_time: float = None,
        end_time: float = None
    ):
        """
        Log a completed span in one call (no stack dependency).

        without worrying about span stack context issues with asyncio.

        Args:
            name: Span name (e.g., "score_framework")
            input_data: Input data for the span
            output_data: Output data for the span
            metadata: Additional metadata
            start_time: Optional start timestamp
            end_time: Optional end timestamp
        """
        if not self.enabled or not self._client:
            return

        try:
            import datetime

            # Create span using SDK's span method directly on current context
            with self._client.start_as_current_span(
                name=name,
                input=input_data,
                metadata=metadata or {}
            ) as span:
                # Update with output
                self._client.update_current_span(output=output_data)

            logger.debug(f"[LANGFUSE::SPAN] Span logged: {name}")
        except Exception as e:
            logger.warning(f"[LANGFUSE::GALAT] Failed to log span: {e}")

    # =========================================================================
    # Generation Logging (for LLM calls with cost tracking)
    # =========================================================================

    def log_generation(
        self,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        usage_details: Dict[str, int] = None,
        metadata: Dict[str, Any] = None,
        messages: Optional[List[Dict]] = None,
        start_time_iso: Optional[str] = None,
        end_time_iso: Optional[str] = None,
    ):
        """
        Log an LLM generation with model, input, output, and optional usage.

        This creates a generation observation that Langfuse can use to:
        1. Track token usage (if usage_details provided or estimated)
        2. Calculate cost based on model pricing definition

        If usage_details is not provided, tokens will be estimated from text length.

        Args:
            name: Generation name (e.g., "planner_llm_call")
            model: Model name (e.g., "gemini-2.0-flash", "gemini-2.5-flash")
            input_text: The prompt/input sent to the LLM (flat string, used for token
                estimation when messages is not provided)
            output_text: The response from the LLM
            usage_details: Optional dict with token counts {"input": N, "output": M, "total": T}
            metadata: Optional additional metadata
            messages: Optional list of {"role": str, "content": str} dicts. When supplied,
                this is passed as the Langfuse generation input instead of input_text,
                giving the UI a proper chat-conversation view with full untruncated content.
            start_time_iso / end_time_iso: optional UTC ISO-8601 strings for ingestion
                ``generation-create`` (faithfulness replay with export timeline).
        """
        if not self.enabled or not self._client:
            return

        try:
            # Structured messages give Langfuse a proper chat-conversation view;
            # flat input_text is the fallback for non-chat calls.
            generation_input = messages if messages is not None else input_text

            # Always use a flat string for token estimation.
            text_for_estimation = (
                "\n".join(
                    f"{m.get('role', '')}: {m.get('content', '')}"
                    for m in messages
                )
                if messages is not None
                else input_text
            )

            # Estimate tokens if not provided
            if usage_details is None:
                input_tokens = self._estimate_tokens(text_for_estimation)
                output_tokens = self._estimate_tokens(output_text)
                usage_details = {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens
                }
            elif "total" not in usage_details:
                # Ensure total is present
                usage_details["total"] = usage_details.get("input", 0) + usage_details.get("output", 0)

            ctx = self._faithfulness_replay_trace_context
            gen_parent = self._faithfulness_generation_parent_id
            parent_for_ingest = gen_parent or (
                ctx.get("parent_span_id") if ctx else None
            )
            if (
                ctx
                and messages is None
                and parent_for_ingest
                and ctx.get("trace_id")
            ):
                err = self._ingestion_generation_create(
                    trace_id=ctx["trace_id"],
                    parent_observation_id=parent_for_ingest,
                    name=name,
                    model=model,
                    generation_input=generation_input,
                    output_text=output_text,
                    usage_details=usage_details,
                    metadata=metadata or {},
                    start_time=start_time_iso,
                    end_time=end_time_iso,
                )
                if err is None:
                    logger.debug(f"[LANGFUSE::INGEST] generation-create ok: {name}")
                    return
                logger.warning(
                    f"[LANGFUSE::INGEST] faithfulness replay ingestion failed ({err}), using SDK fallback"
                )

            gen_kwargs: Dict[str, Any] = {
                "name": name,
                "model": model,
                "input": generation_input,
            }
            if ctx:
                gen_kwargs["trace_context"] = ctx

            with self._client.start_as_current_generation(**gen_kwargs) as gen:
                update_kwargs = {
                    "output": output_text,
                    "metadata": metadata or {},
                    "usage_details": usage_details
                }

                self._client.update_current_generation(**update_kwargs)

        except Exception as e:
            # Log error but don't crash
            logger.warning(f"log_generation failed: {e}")

    def score_trace(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str = None
    ):
        """
        Score a trace using Langfuse 3.x API.

        Args:
            trace_id: Trace ID to score
            name: Score name
            value: Score value (0.0 - 1.0)
            comment: Optional comment
        """
        if not self.enabled or not self._client:
            return

        try:
            self._client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
                data_type="NUMERIC"
            )
        except Exception as e:
            # Log but don't crash
            logger.warning(f"Score creation failed: {e}")

    def flush(self):
        """Flush any pending spans"""
        if self._client: # Changed from self.langfuse to self._client to match existing class attribute
            try:
                self._client.flush()
            except Exception:
                pass

    @contextmanager
    def trace_execution(self, name: str, session_id: str = None, user_id: str = None, metadata: Dict[str, Any] = None):
        """
        Context manager to trace a block of execution.
        Automatically sets parent trace for contained calls.

        Args:
            name: Name of the trace
            session_id: Session ID
            user_id: User ID
            metadata: Metadata dict
        """
        # Need to import contextmanager from functools
        from functools import wraps
        from contextlib import contextmanager

        if not self.enabled:
            yield None
            return

        # Assuming 'self.trace' method exists and returns a TraceWrapper or similar context manager
        # If 'self.trace' does not exist, this will cause an AttributeError.
        # Based on the TraceWrapper class below, it seems 'self.trace' should be a method
        # that creates and returns an instance of TraceWrapper.
        trace = self.trace(
            name=name,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata
        )

        try:
            # Enter trace context
            active_trace = trace.__enter__()

            # Set as parent for this context
            # Assuming self.set_parent_trace and self.clear_parent_trace exist
            # and manage _parent_trace_id and _parent_observation_id
            self.set_parent_trace(trace, session_id=session_id)

            yield active_trace

        finally:
            # Cleanup
            self.clear_parent_trace()
            trace.__exit__(None, None, None)

    def shutdown(self):
        """Shutdown the Langfuse client."""
        if self._client:
            try:
                self._client.shutdown()
            except Exception:
                pass


# =============================================================================
# Singleton Instance
# =============================================================================

_langfuse_client: Optional[LangfuseClient] = None


def get_langfuse() -> LangfuseClient:
    """
    Get or create singleton Langfuse client instance.

    Returns:
        LangfuseClient instance
    """
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = LangfuseClient()
    return _langfuse_client


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    logger.info("Testing Langfuse client...")

    client = get_langfuse()

    if client.enabled:
        logger.info("Langfuse is enabled!")

        # Test trace with context manager
        with client.trace("test_trace", tags=["test"]) as trace:
            logger.info(f"Trace ID: {trace.trace_id}")

            with trace.span("test_span") as span:
                span.update(output={"message": "Hello from test"})

            trace.score("test_score", 0.85)

        client.flush()
        logger.info("Test complete - check Langfuse dashboard")
    else:
        logger.info("Langfuse is not enabled or not available")
