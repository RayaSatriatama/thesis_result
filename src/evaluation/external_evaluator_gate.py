"""Mandatory external-evaluator gate for batch story generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


REQUIRED_METRICS = ("geval", "fables", "ragas")


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


def export_observations(trace_id: str, destination: Path) -> None:
    """Export only one completed source trace to the JSONL format benchmark uses."""
    from langfuse import Langfuse
    from settings import ObservabilityConfig

    public_key = ObservabilityConfig.LANGFUSE_PUBLIC_KEY.strip()
    secret_key = ObservabilityConfig.LANGFUSE_SECRET_KEY.strip()
    host = ObservabilityConfig.LANGFUSE_HOST.rstrip("/")
    if not public_key or not secret_key or not host:
        raise ValueError("Langfuse credentials are required for external evaluator gating")

    client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        response = client.api.observations.get_many(trace_id=trace_id, limit=100, page=page)
        for observation in response.data or []:
            rows.append(_to_jsonable(observation))
        if page >= response.meta.total_pages:
            break
        page += 1
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
) -> tuple[str, ...]:
    """Append three evaluator branches to one source trace and enforce completion."""
    evaluator_ids = evaluator_ids_from_config(config_path)
    observations_dir = output_dir / "observations" / trace_id
    export_observations(trace_id, observations_dir / f"{trace_id}.jsonl")
    benchmark_dir = output_dir / "external_evaluators" / trace_id
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
