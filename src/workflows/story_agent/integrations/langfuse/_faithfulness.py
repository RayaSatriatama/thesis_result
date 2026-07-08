"""
Faithfulness Replay Mixin for Langfuse.

Methods for routing spans/generations to an existing trace during
faithfulness evaluation replays (FABLES workflow).
"""

from typing import Dict, Optional, Any

import re
import secrets

from loguru import logger


class FaithfulnessMixin:
    """Mixin providing faithfulness-replay tracing helpers.

    Expects the consuming class to provide (via ``IngestionMixin`` or directly):
      - ``self._faithfulness_replay_trace_context``
      - ``self._faithfulness_generation_parent_id``
      - ``self._faithfulness_fables_ingestion_start_time``
      - ``self._normalize_trace_id()``  (static)
      - ``self._normalize_span_id()``   (static)
      - ``self._utc_iso_ms()``          (static, from IngestionMixin)
      - ``self._ingestion_span_create()``
      - ``self._ingestion_span_update()``
      - ``self._ingestion_generation_update()``
    """

    # ------------------------------------------------------------------
    # Replay context management
    # ------------------------------------------------------------------

    def set_faithfulness_replay_trace(
        self, trace_id: str, parent_span_id: Optional[str] = None
    ) -> None:
        """Route subsequent spans/generations to an existing trace (replay tooling).

        See https://langfuse.com/docs/observability/sdk/python/instrumentation (trace_context).
        Call :meth:`clear_faithfulness_replay_trace` after the replay run completes.
        """
        tid = self._normalize_trace_id(trace_id)
        ctx: Dict[str, str] = {"trace_id": tid}
        if parent_span_id:
            ctx["parent_span_id"] = self._normalize_span_id(parent_span_id)
        self._faithfulness_replay_trace_context = ctx

    def clear_faithfulness_replay_trace(self) -> None:
        self._faithfulness_replay_trace_context = None
        self._faithfulness_generation_parent_id = None
        self._faithfulness_fables_ingestion_start_time = None

    def set_faithfulness_generation_parent(self, observation_id: Optional[str]) -> None:
        """Force ingestion ``generation-create`` parent to this observation (16-hex Langfuse id).

        Used when ``fables_faithfulness`` is created via ingestion under ``ragas_evaluation`` so
        ``fables_extract_claims`` / ``fables_verify_all_claims`` nest correctly. Cleared by
        :meth:`clear_faithfulness_replay_trace` or :meth:`faithfulness_fables_span_end_ingestion`.
        """
        if not observation_id:
            self._faithfulness_generation_parent_id = None
            return
        norm = self._normalize_span_id(observation_id)
        self._faithfulness_generation_parent_id = (
            norm if len(norm) == 16 and re.fullmatch(r"[0-9a-f]{16}", norm) else None
        )

    # ------------------------------------------------------------------
    # Faithfulness ingestion wrappers
    # ------------------------------------------------------------------

    def faithfulness_ingestion_generation_update(
        self,
        *,
        trace_id: str,
        observation_id: str,
        name: str,
        model: str,
        generation_input: Any,
        output_text: str,
        usage_details: Dict[str, int],
        metadata: Dict[str, Any],
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> None:
        """Update an existing generation (FABLES in-place replay). Logs warning on failure."""
        err = self._ingestion_generation_update(
            trace_id=trace_id,
            observation_id=observation_id,
            model=model,
            generation_input=generation_input,
            output_text=output_text,
            usage_details=usage_details,
            metadata=metadata,
            name=name,
            start_time=start_time,
            end_time=end_time,
        )
        if err:
            logger.warning(f"[LANGFUSE::INGEST] generation-update {name} failed: {err}")

    def faithfulness_ingestion_span_update_output(
        self,
        *,
        trace_id: str,
        observation_id: str,
        output_data: Dict[str, Any],
        name: str = "fables_faithfulness",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> None:
        """span-update output/endTime for an existing FABLES span (in-place replay)."""
        st_raw = (start_time or "").strip()
        en_raw = (end_time or "").strip()
        end_ts = en_raw or st_raw or self._utc_iso_ms()
        start_ts = st_raw or end_ts
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts
        err = self._ingestion_span_update(
            trace_id=trace_id,
            observation_id=observation_id,
            start_time=start_ts,
            end_time=end_ts,
            output_data=output_data,
            name=name,
        )
        if err:
            logger.warning(f"[LANGFUSE::INGEST] span-update fables_faithfulness failed: {err}")

    def faithfulness_fables_span_start_ingestion(
        self,
        *,
        trace_id: str,
        input_data: Dict[str, Any],
        metadata: Dict[str, Any],
        name: str = "fables_faithfulness",
        start_time_iso: Optional[str] = None,
        end_time_iso: Optional[str] = None,
    ) -> Optional[str]:
        """Create ``fables_faithfulness`` via ingestion under replay ctx's ``parent_span_id`` (ragas).

        Sets generation parent so :meth:`log_generation` nests FABLES generations under this span.
        Returns the new 16-hex observation id, or None on failure.
        """
        ctx = self._faithfulness_replay_trace_context
        if not ctx or not ctx.get("parent_span_id") or not ctx.get("trace_id"):
            logger.warning(
                "[LANGFUSE::INGEST] faithfulness_fables_span_start_ingestion: missing replay context"
            )
            return None
        tid = ctx["trace_id"]
        ragas_pid = ctx["parent_span_id"]
        span_id = secrets.token_hex(8)
        ts_fallback = self._utc_iso_ms()
        ts_start = (start_time_iso or "").strip() or ts_fallback
        ts_end = (end_time_iso or "").strip() or ts_start
        if ts_start > ts_end:
            ts_start, ts_end = ts_end, ts_start
        err = self._ingestion_span_create(
            trace_id=tid,
            parent_observation_id=ragas_pid,
            observation_id=span_id,
            name=name,
            start_time=ts_start,
            end_time=ts_end,
            input_data=input_data,
            metadata=metadata,
        )
        if err:
            logger.warning(f"[LANGFUSE::INGEST] fables span-create failed: {err}")
            return None
        self._faithfulness_fables_ingestion_start_time = ts_start
        self.set_faithfulness_generation_parent(span_id)
        logger.debug(f"[LANGFUSE::INGEST] fables span-create ok id={span_id}")
        return span_id

    def faithfulness_fables_span_end_ingestion(
        self,
        *,
        trace_id: str,
        observation_id: str,
        output_data: Dict[str, Any],
        name: str = "fables_faithfulness",
        start_time_iso: Optional[str] = None,
        end_time_iso: Optional[str] = None,
    ) -> None:
        """Close ingestion-based FABLES span and clear temporary generation parent."""
        start_ts = (
            (start_time_iso or "").strip()
            or self._faithfulness_fables_ingestion_start_time
            or self._utc_iso_ms()
        )
        en_raw = (end_time_iso or "").strip()
        end_ts = en_raw or start_ts
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts
        err = self._ingestion_span_update(
            trace_id=trace_id,
            observation_id=observation_id,
            start_time=start_ts,
            end_time=end_ts,
            output_data=output_data,
            name=name,
        )
        if err:
            logger.warning(f"[LANGFUSE::INGEST] fables span-update failed: {err}")
        self.set_faithfulness_generation_parent(None)
        self._faithfulness_fables_ingestion_start_time = None
