"""Build editable benchmark trace overlays without mutating Langfuse history."""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any, Mapping, Sequence


_RESULT_SCORE_NAMES = {
    "geval": (("geval_coherence_normalized", "geval_coherence_normalized"),),
    "fables": (
        ("fables_faithfulness", "fables_faithfulness"),
        ("ragas_standard_faithfulness", "ragas_standard_faithfulness"),
    ),
    "ragas": (
        ("answer_relevancy", "ragas_answer_relevancy"),
        ("context_relevance", "ragas_context_relevance"),
    ),
}


def benchmark_score_values(metric: str, scores: Mapping[str, Any]) -> dict[str, float]:
    """Select the aggregate benchmark scores shown on an evaluator observation."""
    result: dict[str, float] = {}
    for source_name, score_name in _RESULT_SCORE_NAMES.get(metric, ()):
        value = scores.get(source_name)
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            result[score_name] = numeric
    return result


def build_benchmark_trace_overlay(
    rows: Sequence[Mapping[str, Any]], *, benchmark_run_id: str
) -> dict[str, Any]:
    """Build an editable tree that overlays completed judges onto one source trace."""
    if not rows:
        raise ValueError("cannot build a trace overlay without benchmark rows")
    first = rows[0]
    source_trace_id = str(first.get("source_trace_id") or "").strip()
    source_root_id = str(first.get("source_root_observation_id") or "").strip()
    if not source_trace_id or not source_root_id:
        raise ValueError(
            "historical trace export must include a StoryGenerationWorkflow or "
            "BaselineWikiEvalWorkflow root observation"
        )
    if any(
        str(row.get("source_trace_id") or "").strip() != source_trace_id
        or str(row.get("source_root_observation_id") or "").strip() != source_root_id
        for row in rows
    ):
        raise ValueError("a trace overlay may contain only one source trace and root observation")

    evaluators: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in rows:
        evaluator = row.get("evaluator")
        if not isinstance(evaluator, Mapping):
            raise ValueError("benchmark row does not include an evaluator")
        identifier = str(evaluator.get("identifier") or "").strip()
        if not identifier:
            raise ValueError("benchmark evaluator must include an identifier")
        evaluator_node = evaluators.setdefault(
            identifier,
            {
                "id": f"benchmark:{benchmark_run_id}:{identifier}",
                "name": identifier,
                "type": "EVALUATOR",
                "model": evaluator.get("model"),
                "metadata": {"evaluator": dict(evaluator)},
                "scores": {},
                "children": [],
            },
        )
        metric = str(row.get("metric") or "").strip()
        metric_node = {
            "name": metric,
            "type": "EVALUATOR",
            "input": {"source_observation_id": row.get("source_observation_id")},
            "output": {
                "status": row.get("status"),
                "error": row.get("error"),
                "scores": benchmark_score_values(metric, row.get("scores") or {}),
            },
        }
        evaluator_node["children"].append(metric_node)
        evaluator_node["scores"].update(metric_node["output"]["scores"])

    return {
        "schema_version": 1,
        "kind": "langfuse_benchmark_trace_overlay",
        "benchmark_run_id": benchmark_run_id,
        "source_trace_id": source_trace_id,
        "root": {
            "id": source_root_id,
            "name": "StoryGenerationWorkflow",
            "type": "SPAN",
            "children": [
                {
                    "id": f"benchmark:{benchmark_run_id}:external_benchmark_evaluation",
                    "name": "external_benchmark_evaluation",
                    "type": "CHAIN",
                    "children": list(evaluators.values()),
                }
            ],
        },
    }
