"""Mandatory external-evaluator gate for batch story generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable


REQUIRED_METRICS = ("geval", "fables", "ragas")
_SOURCE_ROOT_NAMES = {"StoryGenerationWorkflow", "BaselineWikiEvalWorkflow"}


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "json") and hasattr(value, "dict"):
        return json.loads(value.json())
    return value


def evaluator_ids_from_config(config_path: Path) -> tuple[str, ...]:
    value = json.loads(config_path.read_text(encoding="utf-8"))
    evaluators = value.get("evaluators") if isinstance(value, dict) else None
    ids = tuple(str(item.get("id") or "").strip() for item in evaluators or [])
    if len(ids) != 3 or not all(ids) or len(set(ids)) != 3:
        raise ValueError("external evaluator config must define exactly three unique evaluators")
    return ids


def validate_external_evaluator_results(
    result_path: Path, evaluator_ids: Iterable[str]
) -> tuple[str, ...]:
    """Return missing evaluator:metric pairs; an empty tuple is the completion gate."""
    completed: set[tuple[str, str]] = set()
    if result_path.exists():
        for line in result_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            evaluator = row.get("evaluator") or {}
            identifier = str(evaluator.get("identifier") or "")
            metric = str(row.get("metric") or "")
            if row.get("status") == "completed":
                completed.add((identifier, metric))
    return tuple(
        f"{evaluator_id}:{metric}"
        for evaluator_id in evaluator_ids
        for metric in REQUIRED_METRICS
        if (evaluator_id, metric) not in completed
    )


def has_source_workflow_root(rows: Iterable[dict[str, Any]]) -> bool:
    """Return whether the exported trace contains its evaluatable root."""
    return any(
        str(row.get("id") or "").strip()
        and not str(row.get("parentObservationId") or row.get("parent_observation_id") or "").strip()
        and row.get("name") in _SOURCE_ROOT_NAMES
        for row in rows
    )


def _fetch_observations(client: Any, trace_id: str) -> list[dict[str, Any]]:
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        response = client.api.observations.get_many(trace_id=trace_id, limit=100, page=page)
        rows.extend(_to_jsonable(observation) for observation in response.data or [])
        if page >= response.meta.total_pages:
            return rows
        page += 1


def export_observations(
    trace_id: str,
    destination: Path,
    *,
    max_wait_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
) -> None:
    """Wait for and export one source trace that has an evaluatable root."""
    from langfuse import Langfuse
    from settings import ObservabilityConfig

    public_key = ObservabilityConfig.LANGFUSE_PUBLIC_KEY.strip()
    secret_key = ObservabilityConfig.LANGFUSE_SECRET_KEY.strip()
    host = ObservabilityConfig.LANGFUSE_HOST.rstrip("/")
    if not public_key or not secret_key or not host:
        raise ValueError("Langfuse credentials are required for external evaluator gating")

    client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    deadline = time.monotonic() + max_wait_seconds
    while True:
        rows = _fetch_observations(client, trace_id)
        if has_source_workflow_root(rows):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"source trace root was not available after {max_wait_seconds:.0f}s: {trace_id}"
            )
        time.sleep(min(poll_interval_seconds, max(0.0, deadline - time.monotonic())))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def run_external_evaluator_gate(
    *,
    trace_id: str,
    config_path: Path,
    workspace_root: Path,
    output_dir: Path,
    artifact_root: Path | None = None,
) -> tuple[str, ...]:
    """Append three evaluator branches to one source trace and enforce completion."""
    evaluator_ids = evaluator_ids_from_config(config_path)
    observations_dir = output_dir / "observations" / trace_id
    export_observations(trace_id, observations_dir / f"{trace_id}.jsonl")
    benchmark_dir = (artifact_root or output_dir / "external_evaluators") / trace_id
    command = [
        sys.executable,
        str(workspace_root / "scripts" / "benchmark_openrouter_evaluators.py"),
        "--config",
        str(config_path),
        "--observations-dir",
        str(observations_dir),
        "--output-dir",
        str(benchmark_dir),
    ]
    completed = subprocess.run(command, cwd=workspace_root, env=os.environ.copy())
    if completed.returncode != 0:
        raise RuntimeError(f"external evaluator command failed for trace {trace_id}")
    missing = validate_external_evaluator_results(benchmark_dir / "results.jsonl", evaluator_ids)
    if missing:
        raise RuntimeError("external evaluator gate incomplete: " + ", ".join(missing))
    return evaluator_ids
