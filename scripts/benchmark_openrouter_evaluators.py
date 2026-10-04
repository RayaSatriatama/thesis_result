#!/usr/bin/env python3
"""Benchmark named OpenRouter evaluators against frozen historical exports.

The command is append-only: it reads JSONL observations and writes a new run
directory. It never regenerates source stories. Langfuse reporting is disabled
unless the explicit benchmark configuration enables it.
"""

from __future__ import annotations

import argparse
from contextvars import ContextVar
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from evaluation.openrouter_benchmark import (  # noqa: E402
    BenchmarkConfig,
    OpenRouterModelInspector,
    benchmark_score_values,
    build_benchmark_trace_overlay,
    build_manifest,
    evaluate_fables_sample,
    evaluate_geval_sample,
    evaluate_ragas_sample,
    load_fables_samples,
    load_geval_samples,
    require_openrouter_key,
    run_async,
    run_with_execution,
    smoke_test_tool_round_trip,
    validate_model_for_run,
)


class _BenchmarkEvaluatorObserver:
    """Expose native evaluator steps under one prepared evaluator observation."""

    def __init__(self, *, client: Any, trace_id: str, evaluator_observation_id: str):
        self.client = client
        self.trace_id = trace_id
        self.evaluator_observation_id = evaluator_observation_id
        self.enabled = True
        self._parent_observation_id: ContextVar[str] = ContextVar(
            f"benchmark_parent_{evaluator_observation_id}",
            default=evaluator_observation_id,
        )
        self._spans: dict[str, tuple[Any, Any, Any]] = {}

    def _trace_context(self) -> dict[str, str]:
        return {
            "trace_id": self.trace_id,
            "parent_span_id": self._parent_observation_id.get(),
        }

    def start_span(
        self,
        *,
        name: str,
        input_data: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        context = self.client.start_as_current_observation(
            name=name,
            as_type="span",
            input=input_data,
            metadata=metadata or {},
            trace_context=self._trace_context(),
        )
        observation = context.__enter__()
        span_id = str(observation.id)
        parent_token = self._parent_observation_id.set(span_id)
        self._spans[span_id] = (context, observation, parent_token)
        return span_id

    def end_span(self, span_id: str | None, output_data: Any = None) -> None:
        if not span_id:
            return
        span = self._spans.pop(span_id, None)
        if not span:
            return
        context, observation, parent_token = span
        try:
            update_current_span = getattr(self.client, "update_current_span", None)
            if update_current_span:
                update_current_span(output=output_data)
            elif hasattr(observation, "update"):
                observation.update(output=output_data)
        finally:
            self._parent_observation_id.reset(parent_token)
            context.__exit__(None, None, None)

    def log_generation(
        self,
        *,
        name: str,
        model: str,
        input_text: str,
        output_text: str,
        usage_details: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
        messages: list[dict[str, Any]] | None = None,
        **_unused: Any,
    ) -> None:
        context = self.client.start_as_current_observation(
            name=name,
            as_type="generation",
            model=model,
            input=messages if messages is not None else input_text,
            output=output_text,
            usage_details=usage_details,
            metadata=metadata or {},
            trace_context=self._trace_context(),
        )
        with context:
            pass

    def create_score(self, **_unused: Any) -> None:
        """Scores are consolidated on the model evaluator after all metric calls finish."""


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Explicit benchmark JSON config.")
    parser.add_argument(
        "--observations-dir",
        type=Path,
        help="Override source.observations_dir in the config.",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="New append-only run directory.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum frozen samples per evaluator (0 = all).")
    parser.add_argument("--dry-run", action="store_true", help="Preflight and write manifest without inference.")
    parser.add_argument(
        "--smoke-tools",
        action="store_true",
        help="Run one two-step client-tool test. It is blocked unless the model is listed free and supports tools.",
    )
    return parser.parse_args()


def _resolve_observations_dir(args: argparse.Namespace, config: BenchmarkConfig) -> Path:
    configured = config.source.get("observations_dir")
    path = args.observations_dir or (ROOT / configured if configured else ROOT / "Eval_Data/Observations")
    if not path.is_dir():
        raise ValueError(f"observations directory does not exist: {path}")
    return path


def _preflight(config: BenchmarkConfig, smoke_tools: bool) -> dict:
    inspector = OpenRouterModelInspector()
    inspected = {}
    for target in config.evaluators:
        info = inspector.inspect(target.model)
        required = set(target.required_parameters)
        if smoke_tools:
            required.add("tools")
        errors = validate_model_for_run(info, required, target.require_free or smoke_tools)
        if errors:
            raise ValueError("; ".join(errors))
        inspected[target.identifier] = info
    if config.ragas_embedding:
        info = inspector.inspect(config.ragas_embedding.model)
        errors = validate_model_for_run(info, set(), config.ragas_embedding.require_free)
        if errors:
            raise ValueError("; ".join(errors))
        inspected["ragas_embedding"] = info
    return inspected


class _LangfuseBenchmarkReporter:
    """Publish new runs or write an editable overlay for immutable historical traces."""

    def __init__(self, config: BenchmarkConfig, benchmark_run_id: str, output_dir: Path):
        self.config = config
        self.benchmark_run_id = benchmark_run_id
        self.output_dir = output_dir
        self.score_timestamp = datetime.now(timezone.utc)
        self._live_observers: dict[tuple[str, str], _BenchmarkEvaluatorObserver] = {}
        if config.langfuse.mode == "local_export":
            self.client = None
            return
        if not config.langfuse.enabled:
            self.client = None
            return
        if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
            raise ValueError("Langfuse reporting requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
        from langfuse import Langfuse

        self.client = Langfuse()

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def record(self, rows: list[dict[str, Any]]) -> None:
        if self.config.langfuse.mode == "local_export":
            self._write_local_overlay(rows)
            return
        if not self.client:
            return
        if self.config.langfuse.mode == "source_trace":
            self._record_on_source_trace(rows)
            return
        self._record_as_separate_trace(rows)

    def prepare_source_trace_observers(
        self, samples_by_metric: dict[str, list[Any]]
    ) -> dict[tuple[str, str], _BenchmarkEvaluatorObserver]:
        """Create stable model parents before concurrent native evaluator work starts."""
        if self.config.langfuse.mode != "source_trace" or not self.client:
            return {}
        sources: dict[str, dict[str, Any]] = {}
        for samples in samples_by_metric.values():
            for sample in samples:
                source_trace_id = str(sample.trace_id or sample.source_observation_id)
                source_root_observation_id = str(sample.source_root_observation_id or "").strip()
                if not source_root_observation_id:
                    raise ValueError("source_trace mode requires StoryGenerationWorkflow root observation id")
                source = sources.setdefault(
                    source_trace_id,
                    {"root_id": source_root_observation_id, "observation_ids": set()},
                )
                if source["root_id"] != source_root_observation_id:
                    raise ValueError("one source trace cannot have multiple StoryGenerationWorkflow roots")
                source["observation_ids"].add(sample.source_observation_id)

        for source_trace_id, source in sources.items():
            with self.client.start_as_current_observation(
                name="external_benchmark_evaluation",
                as_type="chain",
                trace_context={"trace_id": source_trace_id, "parent_span_id": source["root_id"]},
                input={"source_trace_id": source_trace_id, "benchmark_run_id": self.benchmark_run_id},
                metadata={"benchmark_run_id": self.benchmark_run_id},
            ) as chain:
                for target in self.config.evaluators:
                    evaluator = target.to_dict()
                    provider_preferences = dict(target.provider_preferences)
                    only = provider_preferences.get("only")
                    provider = only[0] if isinstance(only, list) and len(only) == 1 else "openrouter"
                    metadata = {
                        "benchmark_run_id": self.benchmark_run_id,
                        "source_trace_id": source_trace_id,
                        "source_observation_ids": sorted(source["observation_ids"]),
                        "evaluator_id": target.identifier,
                        "evaluator_model": target.model,
                        "provider": provider,
                        "provider_preferences": provider_preferences,
                        "metrics": list(self.config.metrics),
                    }
                    with self.client.start_as_current_observation(
                        name=target.identifier,
                        as_type="evaluator",
                        model=target.model,
                        input={"source_trace_id": source_trace_id, "metrics": list(self.config.metrics)},
                        metadata=metadata,
                        trace_context={"trace_id": source_trace_id, "parent_span_id": chain.id},
                    ) as observation:
                        self._live_observers[(source_trace_id, target.identifier)] = (
                            _BenchmarkEvaluatorObserver(
                                client=self.client,
                                trace_id=source_trace_id,
                                evaluator_observation_id=observation.id,
                            )
                        )
        return dict(self._live_observers)

    def _write_local_overlay(self, rows: list[dict[str, Any]]) -> None:
        overlay = build_benchmark_trace_overlay(rows, benchmark_run_id=self.benchmark_run_id)
        source_trace_id = overlay["source_trace_id"]
        overlay_dir = self.output_dir / "trace_overlays"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        _write_json(overlay_dir / f"{source_trace_id}.json", overlay)

    def _source_trace_details(self, rows: list[dict[str, Any]]) -> tuple[str, str, dict[str, Any]]:
        first = rows[0]
        source_trace_id = str(first.get("source_trace_id") or first["source_observation_id"])
        source_root_observation_id = str(first.get("source_root_observation_id") or "").strip()
        if not source_root_observation_id:
            raise ValueError("source_trace mode requires StoryGenerationWorkflow root observation id")
        return source_trace_id, source_root_observation_id, first

    def _score_values(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        return {
            name: value
            for row in rows
            for name, value in benchmark_score_values(row["metric"], row.get("scores", {})).items()
        }

    def _metadata(self, rows: list[dict[str, Any]], source_trace_id: str, evaluator: dict[str, Any]) -> dict[str, Any]:
        provider_preferences = evaluator["provider_preferences"]
        only = provider_preferences.get("only")
        provider = only[0] if isinstance(only, list) and len(only) == 1 else "openrouter"
        return {
            "benchmark_run_id": self.benchmark_run_id,
            "source_trace_id": source_trace_id,
            "source_observation_ids": [row["source_observation_id"] for row in rows],
            "evaluator_id": evaluator["identifier"],
            "evaluator_model": evaluator["model"],
            "provider": provider,
            "provider_preferences": provider_preferences,
            "metrics": [row["metric"] for row in rows],
        }

    def _record_on_source_trace(self, rows: list[dict[str, Any]]) -> None:
        source_trace_id, source_root_observation_id, _ = self._source_trace_details(rows)
        if self._live_observers:
            self._record_scores_on_prepared_source_trace(rows, source_trace_id)
            return
        from langfuse import propagate_attributes

        session_id = self.config.langfuse.session_id_template.format(source_trace_id=source_trace_id)
        by_evaluator: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_evaluator.setdefault(row["evaluator"]["identifier"], []).append(row)
        with propagate_attributes(session_id=session_id):
            with self.client.start_as_current_observation(
                name="external_benchmark_evaluation",
                as_type="chain",
                trace_context={"trace_id": source_trace_id, "parent_span_id": source_root_observation_id},
                input={"source_trace_id": source_trace_id, "benchmark_run_id": self.benchmark_run_id},
                metadata={"benchmark_run_id": self.benchmark_run_id},
            ):
                for evaluator_rows in by_evaluator.values():
                    evaluator = evaluator_rows[0]["evaluator"]
                    metadata = self._metadata(evaluator_rows, source_trace_id, evaluator)
                    score_values = self._score_values(evaluator_rows)
                    with self.client.start_as_current_observation(
                        name=evaluator["identifier"],
                        as_type="evaluator",
                        model=evaluator["model"],
                        input={"source_trace_id": source_trace_id, "metrics": metadata["metrics"]},
                        output={
                            "status": {row["metric"]: row["status"] for row in evaluator_rows},
                            "error": {row["metric"]: row["error"] for row in evaluator_rows if row["error"]},
                            "scores": score_values,
                        },
                        metadata=metadata,
                    ) as observation:
                        for row in evaluator_rows:
                            with self.client.start_as_current_observation(
                                name=row["metric"],
                                as_type="evaluator",
                                input={"source_observation_id": row["source_observation_id"]},
                                output={"status": row["status"], "error": row["error"]},
                            ):
                                pass
                        for name, value in score_values.items():
                            self.client.create_score(
                                trace_id=source_trace_id,
                                observation_id=observation.id,
                                name=name,
                                value=value,
                                config_id=(self.config.langfuse.score_config_ids or {}).get(name),
                                score_id=(
                                    f"{self.benchmark_run_id}:{source_trace_id}:"
                                    f"{evaluator['identifier']}:{name}"
                                ),
                                data_type="NUMERIC",
                                metadata=metadata,
                                timestamp=self.score_timestamp,
                            )

    def _record_scores_on_prepared_source_trace(
        self, rows: list[dict[str, Any]], source_trace_id: str
    ) -> None:
        by_evaluator: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_evaluator.setdefault(row["evaluator"]["identifier"], []).append(row)
        for evaluator_id, evaluator_rows in by_evaluator.items():
            observer = self._live_observers.get((source_trace_id, evaluator_id))
            if not observer:
                raise ValueError(f"missing prepared evaluator observation: {source_trace_id}/{evaluator_id}")
            metadata = self._metadata(
                evaluator_rows, source_trace_id, evaluator_rows[0]["evaluator"]
            )
            for name, value in self._score_values(evaluator_rows).items():
                self.client.create_score(
                    trace_id=source_trace_id,
                    observation_id=observer.evaluator_observation_id,
                    name=name,
                    value=value,
                    config_id=(self.config.langfuse.score_config_ids or {}).get(name),
                    score_id=(
                        f"{self.benchmark_run_id}:{source_trace_id}:{evaluator_id}:{name}"
                    ),
                    data_type="NUMERIC",
                    metadata=metadata,
                    timestamp=self.score_timestamp,
                )

    def _record_as_separate_trace(self, rows: list[dict[str, Any]]) -> None:
        from langfuse import propagate_attributes

        first = rows[0]
        source_trace_id = first.get("source_trace_id") or first["source_observation_id"]
        session_id = self.config.langfuse.session_id_template.format(source_trace_id=source_trace_id)
        evaluator = first["evaluator"]
        score_values = self._score_values(rows)
        metadata = self._metadata(rows, source_trace_id, evaluator)
        with propagate_attributes(session_id=session_id):
            with self.client.start_as_current_observation(
                name=f"{self.config.langfuse.trace_name_prefix}/{evaluator['identifier']}",
                as_type="evaluator",
                input={"source_trace_id": source_trace_id, "metrics": metadata["metrics"]},
                output={
                    "status": {row["metric"]: row["status"] for row in rows},
                    "error": {row["metric"]: row["error"] for row in rows if row["error"]},
                    "scores": score_values,
                },
                metadata=metadata,
            ) as observation:
                for name, value in score_values.items():
                    self.client.create_score(
                        trace_id=observation.trace_id,
                        observation_id=observation.id,
                        name=name,
                        value=value,
                        config_id=(self.config.langfuse.score_config_ids or {}).get(name),
                        score_id=(
                            f"{self.benchmark_run_id}:{source_trace_id}:"
                            f"{evaluator['identifier']}:{name}"
                        ),
                        data_type="NUMERIC",
                        metadata=metadata,
                        timestamp=self.score_timestamp,
                    )

    def flush(self) -> None:
        if self.client:
            self.client.flush()


async def _evaluate_target(
    target: Any,
    *,
    args: argparse.Namespace,
    config: BenchmarkConfig,
    samples_by_metric: dict[str, list[Any]],
    api_key: str,
    base_url: str,
    observers: dict[tuple[str, str], _BenchmarkEvaluatorObserver] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if args.smoke_tools:
        smoke = await smoke_test_tool_round_trip(target, api_key=api_key, base_url=base_url)
        _write_json(args.output_dir / f"smoke-{target.identifier}.json", smoke)
        if smoke["status"] != "completed":
            raise RuntimeError(f"tool smoke failed for {target.identifier}: {smoke.get('error')}")
    for metric, samples in samples_by_metric.items():
        for sample in samples:
            source_trace_id = str(sample.trace_id or sample.source_observation_id)
            observer = (observers or {}).get((source_trace_id, target.identifier))
            if metric == "geval":
                outcomes = {
                    "geval": await evaluate_geval_sample(
                        sample, target, api_key=api_key, base_url=base_url, observer=observer
                    )
                }
            elif "ragas" in config.metrics:
                outcome = await evaluate_ragas_sample(
                    sample,
                    target,
                    config.ragas_embedding,
                    api_key=api_key,
                    base_url=base_url,
                    observer=observer,
                )
                outcomes = {
                    group: {
                        "status": outcome["status"],
                        "started_at": outcome["started_at"],
                        "scores": scores,
                        "error": outcome["error"],
                    }
                    for group, scores in outcome["score_groups"].items()
                    if group in config.metrics
                }
            else:
                outcomes = {
                    "fables": await evaluate_fables_sample(
                        sample, target, api_key=api_key, base_url=base_url, observer=observer
                    )
                }
            for result_metric, outcome in outcomes.items():
                row = {
                    "schema_version": 1,
                    "metric": result_metric,
                    "source_observation_id": sample.source_observation_id,
                    "source_trace_id": sample.trace_id,
                    "source_root_observation_id": sample.source_root_observation_id,
                    "source_evaluator_model": sample.source_evaluator_model,
                    "evaluator": target.to_dict(),
                    **outcome,
                }
                if metric == "ragas_fables":
                    row["context_origin"] = sample.context_origin
                rows.append(row)
    return rows


def main() -> int:
    args = _arguments()
    if args.limit < 0:
        raise ValueError("--limit must be zero or positive")
    config = BenchmarkConfig.from_json(args.config)
    observations_dir = _resolve_observations_dir(args, config)
    samples_by_metric = {}
    if "geval" in config.metrics:
        samples = load_geval_samples(observations_dir)
        samples_by_metric["geval"] = samples[: args.limit] if args.limit else samples
    if {"fables", "ragas"}.intersection(config.metrics):
        samples = load_fables_samples(observations_dir)
        samples_by_metric["ragas_fables"] = samples[: args.limit] if args.limit else samples
    if not any(samples_by_metric.values()):
        raise ValueError("no valid frozen samples found for the requested metrics")
    inspected = _preflight(config, args.smoke_tools)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = build_manifest(
        config, inspected, sum(len(samples) for samples in samples_by_metric.values()), dry_run=args.dry_run
    )
    manifest["effective_required_parameters"] = sorted(
        {
            *(
                parameter
                for target in config.evaluators
                for parameter in target.required_parameters
            ),
            *( ["tools"] if args.smoke_tools else [] ),
        }
    )
    manifest["sample_counts"] = {
        **({"geval": len(samples_by_metric["geval"])} if "geval" in samples_by_metric else {}),
        **(
            {
                metric: len(samples_by_metric["ragas_fables"])
                for metric in ("fables", "ragas")
                if metric in config.metrics
            }
            if "ragas_fables" in samples_by_metric
            else {}
        ),
    }
    _write_json(args.output_dir / "manifest.json", manifest)

    if args.dry_run:
        print(
            f"dry run: {sum(len(samples) for samples in samples_by_metric.values())} frozen samples, "
            f"{len(config.evaluators)} evaluator(s)"
        )
        return 0

    api_key = require_openrouter_key()
    base_url = "https://openrouter.ai/api/v1"
    results_path = args.output_dir / "results.jsonl"
    reporter = _LangfuseBenchmarkReporter(config, args.output_dir.name, args.output_dir)
    observers = reporter.prepare_source_trace_observers(samples_by_metric)
    target_rows = run_async(
        run_with_execution(
            (
                _evaluate_target(
                    target,
                    args=args,
                    config=config,
                    samples_by_metric=samples_by_metric,
                    api_key=api_key,
                    base_url=base_url,
                    observers=observers,
                )
                for target in config.evaluators
            ),
            config.execution,
        )
    )
    with results_path.open("w", encoding="utf-8") as handle:
        by_source: dict[str, list[dict[str, Any]]] = {}
        for rows in target_rows:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                source_key = row.get("source_trace_id") or row["source_observation_id"]
                by_source.setdefault(source_key, []).append(row)
        for source_rows in by_source.values():
            reporter.record(source_rows)
    reporter.flush()
    print(
        f"completed: {sum(len(samples) for samples in samples_by_metric.values())} frozen samples "
        f"written to {results_path}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        print(f"benchmark aborted: {exc}", file=sys.stderr)
        raise SystemExit(2)
