"""
Langfuse Ingestion Mixin.

Low-level HTTP methods for the Langfuse ingestion API (/api/public/ingestion).
Used for direct trace/span/generation CRUD when the Python SDK's context-based
API is insufficient (e.g., faithfulness replay with explicit parentObservationId).
"""

from typing import Dict, List, Optional, Any

import base64
import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loguru import logger

from settings import ObservabilityConfig


class IngestionMixin:
    """Mixin providing low-level Langfuse ingestion HTTP helpers.

    Expects the consuming class to define:
      - ``self._faithfulness_replay_trace_context``
      - ``self._normalize_trace_id()``  (static)
      - ``self._normalize_span_id()``   (static)
    """

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        Estimate token count from text.

        Uses approximate ratio of 1 token per 4 characters for English/Indonesian.
        This is a rough estimate - Gemini models may vary.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        # Approximate: 1 token ~ 4 characters (common heuristic)
        # For more accuracy, could use tiktoken or model-specific tokenizer
        return max(1, len(text) // 4)

    # ------------------------------------------------------------------
    # Timestamp helper
    # ------------------------------------------------------------------

    @staticmethod
    def _utc_iso_ms() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # ------------------------------------------------------------------
    # Core HTTP poster
    # ------------------------------------------------------------------

    @staticmethod
    def _ingestion_post_batch(body: Dict[str, Any]) -> Optional[str]:
        """POST /api/public/ingestion. Returns None on success, else error string."""
        host = (ObservabilityConfig.LANGFUSE_HOST or "").strip().rstrip("/")
        pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
        sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()
        if not host or not pk or not sk:
            return "missing LANGFUSE_HOST or keys"
        try:
            auth = base64.b64encode(f"{pk}:{sk}".encode()).decode("ascii")
            req = Request(
                f"{host}/api/public/ingestion",
                data=json.dumps(body, default=str).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {auth}",
                },
                method="POST",
            )
            with urlopen(req, timeout=60.0) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw) if raw else {}
            errs = out.get("errors") or []
            if errs:
                return f"ingestion errors: {errs[:3]}"
            return None
        except HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = str(e)
            return f"HTTP {e.code}: {detail}"
        except URLError as e:
            return f"URL error: {e}"
        except Exception as e:
            return str(e)

    # ------------------------------------------------------------------
    # Trace upsert
    # ------------------------------------------------------------------

    def ingestion_trace_upsert(
        self,
        *,
        trace_id: str,
        name: str,
        input: Any,
        output: Any,
        timestamp: Optional[str] = None,
        environment: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        public: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Upsert trace-level name, input, output via ``trace-create`` ingestion (legacy API).

        Langfuse merges on trace ``id``. Use after faithfulness replay so the trace row
        shows ``StoryGenerationWorkflow`` (or your workflow name) instead of inheriting
        focus from the last nested observation.

        Pass ``timestamp=None`` (default) so the event time is **now**: replay should not
        reuse the original trace timestamp, or list/detail views may keep showing the latest
        child generation as trace input/output.
        """
        tid = self._normalize_trace_id(trace_id)
        if len(tid) != 32 or not re.fullmatch(r"[0-9a-f]{32}", tid):
            return f"invalid trace_id for trace upsert: {trace_id!r}"

        ts = timestamp or self._utc_iso_ms()
        event_id = str(uuid.uuid4())
        body_payload: Dict[str, Any] = {
            "id": tid,
            "timestamp": ts,
            "name": name,
            "input": input,
            "output": output,
        }
        if environment:
            body_payload["environment"] = environment
        if user_id is not None:
            body_payload["userId"] = user_id
        if session_id is not None:
            body_payload["sessionId"] = session_id
        if tags is not None:
            body_payload["tags"] = tags
        if public is not None:
            body_payload["public"] = public
        if metadata is not None:
            body_payload["metadata"] = metadata

        envelope = {
            "batch": [
                {
                    "id": event_id,
                    "timestamp": ts,
                    "type": "trace-create",
                    "body": body_payload,
                }
            ]
        }
        err = self._ingestion_post_batch(envelope)
        if err is None:
            logger.debug(f"[LANGFUSE::INGEST] trace-create upsert ok: {name} trace={tid[:12]}…")
        return err

    # ------------------------------------------------------------------
    # Generation create / update
    # ------------------------------------------------------------------

    def _ingestion_generation_create(
        self,
        *,
        trace_id: str,
        parent_observation_id: str,
        name: str,
        model: str,
        generation_input: Any,
        output_text: str,
        usage_details: Dict[str, int],
        metadata: Dict[str, Any],
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Optional[str]:
        """POST /api/public/ingestion generation-create with explicit parentObservationId.

        The Langfuse Python SDK marks observations created via ``trace_context`` with
        ``langfuse.internal.as_root``, which can flatten generations in the UI. Ingestion
        keeps the tree under the existing parent span (faithfulness replay).
        Returns None on success, or an error string.
        """
        tid = self._normalize_trace_id(trace_id)
        pid = self._normalize_span_id(parent_observation_id)
        if len(tid) != 32 or not re.fullmatch(r"[0-9a-f]{32}", tid):
            return f"invalid trace_id for ingestion: {trace_id!r}"
        if len(pid) != 16 or not re.fullmatch(r"[0-9a-f]{16}", pid):
            return f"invalid parent_observation_id for ingestion: {parent_observation_id!r}"

        obs_id = secrets.token_hex(8)
        event_id = str(uuid.uuid4())
        ts_now = self._utc_iso_ms()
        ts_start = (start_time or "").strip() or ts_now
        ts_end = (end_time or "").strip() or ts_start
        if ts_start > ts_end:
            ts_start, ts_end = ts_end, ts_start
        body: Dict[str, Any] = {
            "batch": [
                {
                    "id": event_id,
                    "timestamp": ts_start,
                    "type": "generation-create",
                    "body": {
                        "id": obs_id,
                        "traceId": tid,
                        "parentObservationId": pid,
                        "name": name,
                        "startTime": ts_start,
                        "endTime": ts_end,
                        "model": model,
                        "input": generation_input,
                        "output": output_text,
                        "metadata": metadata or {},
                        "usage": {
                            "promptTokens": usage_details.get("input", 0),
                            "completionTokens": usage_details.get("output", 0),
                            "totalTokens": usage_details.get("total", 0),
                        },
                    },
                }
            ]
        }
        return self._ingestion_post_batch(body)

    def _ingestion_generation_update(
        self,
        *,
        trace_id: str,
        observation_id: str,
        model: str,
        generation_input: Any,
        output_text: str,
        usage_details: Dict[str, int],
        metadata: Dict[str, Any],
        name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Optional[str]:
        """POST generation-update for an existing observation. Returns None on success.

        Pass explicit ``start_time`` / ``end_time``. If only one is set, the other copies it
        (never default ``end`` to "now" while ``start`` is set -- that widens duration when
        ClickHouse keeps an older ``start_time`` on merge).
        """
        tid = self._normalize_trace_id(trace_id)
        oid = self._normalize_span_id(observation_id)
        if len(tid) != 32 or not re.fullmatch(r"[0-9a-f]{32}", tid):
            return f"invalid trace_id for generation-update: {trace_id!r}"
        if len(oid) != 16 or not re.fullmatch(r"[0-9a-f]{16}", oid):
            return f"invalid observation id for generation-update: {observation_id!r}"

        ts_now = self._utc_iso_ms()
        st_raw = (start_time or "").strip()
        en_raw = (end_time or "").strip()
        # Avoid defaulting end to "now" when only start is set -- that merges with an
        # immutable old ClickHouse start_time and explodes trace duration in the UI.
        ts_end = en_raw or st_raw or ts_now
        ts_start = st_raw or ts_end
        if ts_start > ts_end:
            ts_start, ts_end = ts_end, ts_start
        event_id = str(uuid.uuid4())
        body_payload: Dict[str, Any] = {
            "id": oid,
            "traceId": tid,
            "environment": "default",
            "startTime": ts_start,
            "endTime": ts_end,
            "completionStartTime": ts_start,
            "model": model,
            "input": generation_input,
            "output": output_text,
            "metadata": metadata or {},
            "usage": {
                "promptTokens": usage_details.get("input", 0),
                "completionTokens": usage_details.get("output", 0),
                "totalTokens": usage_details.get("total", 0),
            },
        }
        if name:
            body_payload["name"] = name
        body: Dict[str, Any] = {
            "batch": [
                {
                    "id": event_id,
                    "timestamp": ts_end,
                    "type": "generation-update",
                    "body": body_payload,
                }
            ]
        }
        return self._ingestion_post_batch(body)

    # ------------------------------------------------------------------
    # Span create / update
    # ------------------------------------------------------------------

    def _ingestion_span_create(
        self,
        *,
        trace_id: str,
        parent_observation_id: str,
        observation_id: str,
        name: str,
        start_time: str,
        end_time: str,
        input_data: Any,
        metadata: Dict[str, Any],
        environment: str = "default",
    ) -> Optional[str]:
        """POST span-create under an existing parent. Returns None on success, else error string."""
        tid = self._normalize_trace_id(trace_id)
        pid = self._normalize_span_id(parent_observation_id)
        oid = self._normalize_span_id(observation_id)
        if len(tid) != 32 or not re.fullmatch(r"[0-9a-f]{32}", tid):
            return f"invalid trace_id for span-create: {trace_id!r}"
        if len(pid) != 16 or not re.fullmatch(r"[0-9a-f]{16}", pid):
            return f"invalid parent_observation_id for span-create: {parent_observation_id!r}"
        if len(oid) != 16 or not re.fullmatch(r"[0-9a-f]{16}", oid):
            return f"invalid observation id for span-create: {observation_id!r}"

        event_id = str(uuid.uuid4())
        body: Dict[str, Any] = {
            "batch": [
                {
                    "id": event_id,
                    "timestamp": start_time,
                    "type": "span-create",
                    "body": {
                        "id": oid,
                        "traceId": tid,
                        "parentObservationId": pid,
                        "name": name,
                        "startTime": start_time,
                        "endTime": end_time,
                        "environment": environment,
                        "input": input_data,
                        "metadata": metadata or {},
                    },
                }
            ]
        }
        return self._ingestion_post_batch(body)

    def _ingestion_span_update(
        self,
        *,
        trace_id: str,
        observation_id: str,
        start_time: str,
        end_time: str,
        output_data: Any,
        name: Optional[str] = None,
        environment: str = "default",
        event_timestamp: Optional[str] = None,
    ) -> Optional[str]:
        """POST span-update (end time + output). Returns None on success, else error string."""
        tid = self._normalize_trace_id(trace_id)
        oid = self._normalize_span_id(observation_id)
        if len(tid) != 32 or not re.fullmatch(r"[0-9a-f]{32}", tid):
            return f"invalid trace_id for span-update: {trace_id!r}"
        if len(oid) != 16 or not re.fullmatch(r"[0-9a-f]{16}", oid):
            return f"invalid observation id for span-update: {observation_id!r}"

        event_id = str(uuid.uuid4())
        payload: Dict[str, Any] = {
            "id": oid,
            "traceId": tid,
            "startTime": start_time,
            "endTime": end_time,
            "environment": environment,
            # Langfuse ingestion expects ``output`` as a JSON string for spans on some deployments.
            # Generations accept structured outputs, but span-update can be ignored unless serialized.
            "output": (
                json.dumps(output_data, ensure_ascii=False, default=str)
                if isinstance(output_data, (dict, list))
                else output_data
            ),
        }
        if name:
            payload["name"] = name
        ts_event = (event_timestamp or "").strip() or end_time
        body = {
            "batch": [
                {
                    "id": event_id,
                    "timestamp": ts_event,
                    "type": "span-update",
                    "body": payload,
                }
            ]
        }
        return self._ingestion_post_batch(body)
