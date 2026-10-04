#!/usr/bin/env python3
"""Run WikiEval stories through the full story API and persist checkpoints.

The default selection is 50 WikiEval items in both supported languages, or
100 stories per generator model. Each model must use its own output directory.
The API process controls provider routing through its environment; ``model`` is
sent per request because the workflow API supports a request-level model.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable, Iterator, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "dataset" / "wikiEval_all.json"


@dataclass(frozen=True)
class SSEEvent:
    event: str
    data: dict[str, Any]


@dataclass(frozen=True)
class WikiEvalRow:
    source: str
    question: str
    answer: str
    context_v1: list[str]
    context_v2: list[str]


def parse_sse_events(text: str) -> list[SSEEvent]:
    """Parse complete SSE blocks while tolerating CRLF and non-JSON events."""
    events: list[SSEEvent] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())
        if not data_lines:
            continue
        raw_data = "\n".join(data_lines)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            data = {"raw": raw_data}
        if isinstance(data, dict):
            events.append(SSEEvent(event=event_name, data=data))
    return events


def build_request_payload(
    *,
    question: str,
    language: str,
    model: str,
    target_age: str,
    story_length: str,
) -> dict[str, Any]:
    clean_question = (question or "").replace("Question: ", "").strip()
    prefix = "Create an educational story that helps students understand" if language == "English" else "Buat cerita edukatif yang membantu siswa memahami"
    return {
        "prompt": f"{prefix}: {clean_question}",
        "target_age": target_age,
        "language": language,
        "story_length": story_length,
        "active_writers": ["text"],
        "model": model,
    }


def load_dataset(path: Path) -> list[WikiEvalRow]:
    rows: list[WikiEvalRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            rows.append(
                WikiEvalRow(
                    source=str(value.get("source", "")),
                    question=str(value.get("question", "")),
                    answer=str(value.get("answer", "")),
                    context_v1=list(value.get("context_v1", []) or []),
                    context_v2=list(value.get("context_v2", []) or []),
                )
            )
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def _selected_runs(rows: Sequence[WikiEvalRow], languages: Sequence[str], start: int, limit: int) -> Iterator[tuple[int, WikiEvalRow, str]]:
    selected = rows[start:] if limit <= 0 else rows[start : start + limit]
    for item_idx, row in enumerate(selected, start=start):
        for language in languages:
            yield item_idx, row, language


def _read_checkpoint(path: Path) -> tuple[list[dict[str, Any]], set[tuple[int, str]]]:
    if not path.exists():
        return [], set()
    results: list[dict[str, Any]] = []
    done: set[tuple[int, str]] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            results.append(row)
            if row.get("status") == "completed" and row.get("external_evaluation_status") == "completed":
                done.add((int(row["item_idx"]), str(row["language"])))
    return results, done


def _append_checkpoint(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")


def _pending_external_evaluations(
    results: Iterable[dict[str, Any]],
) -> dict[tuple[int, str], dict[str, Any]]:
    """Keep the latest generated story that still needs external evaluation."""
    pending: dict[tuple[int, str], dict[str, Any]] = {}
    for row in results:
        if "item_idx" not in row or "language" not in row:
            continue
        key = (int(row["item_idx"]), str(row["language"]))
        if row.get("status") == "completed" and row.get("external_evaluation_status") == "completed":
            pending.pop(key, None)
        elif row.get("final_story") and row.get("trace_id"):
            pending[key] = row
    return pending


def _request_story(
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
) -> list[SSEEvent]:
    import httpx

    headers = {"Accept": "text/event-stream"}
    if api_key:
        headers["X-API-Key"] = api_key
    with httpx.Client(timeout=timeout) as client:
        with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/api/workflow/generate",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            chunks = list(response.iter_text())
    return parse_sse_events("".join(chunks))


def run(args: argparse.Namespace) -> int:
    from evaluation.external_evaluator_gate import evaluator_ids_from_config

    evaluator_ids_from_config(Path(args.external_evaluator_config))
    rows = load_dataset(Path(args.dataset))
    languages = tuple(args.languages.split(","))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out_dir / "results.jsonl"
    results, done = _read_checkpoint(checkpoint_path)
    pending = _pending_external_evaluations(results)
    api_key = args.api_key or os.getenv("API_KEY", "")
    retry_artifact_root = out_dir / f"external_evaluator_retries_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"

    for item_idx, row, language_code in _selected_runs(rows, languages, args.start, args.limit):
        key = (item_idx, language_code)
        if key in done:
            continue
        prior = pending.get(key)
        if prior:
            result = dict(prior)
            result["external_evaluation_retry_started_at"] = datetime.now(timezone.utc).isoformat()
            try:
                from evaluation.external_evaluator_gate import run_external_evaluator_gate

                evaluator_ids = run_external_evaluator_gate(
                    trace_id=str(result["trace_id"]),
                    config_path=Path(args.external_evaluator_config),
                    workspace_root=ROOT,
                    output_dir=out_dir,
                    artifact_root=retry_artifact_root,
                )
            except Exception as exc:
                result["external_evaluation_status"] = "failed"
                result["external_evaluation_error"] = repr(exc)
            else:
                prior_error = result.pop("error", None)
                if prior_error:
                    result["external_evaluation_previous_error"] = prior_error
                result["external_evaluator_ids"] = list(evaluator_ids)
                result["external_evaluation_status"] = "completed"
                result.pop("external_evaluation_error", None)
            result["finished_at"] = datetime.now(timezone.utc).isoformat()
            _append_checkpoint(checkpoint_path, result)
            results.append(result)
            if result.get("external_evaluation_status") == "completed":
                done.add(key)
            (out_dir / "results.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)
            continue
        language = "English" if language_code == "en" else "Indonesian"
        payload = build_request_payload(
            question=row.question,
            language=language,
            model=args.model,
            target_age=args.target_age,
            story_length=args.story_length,
        )
        started = datetime.now(timezone.utc)
        result: dict[str, Any] = {
            "item_idx": item_idx,
            "source": row.source,
            "question": row.question,
            "answer": row.answer,
            "context_v1": row.context_v1,
            "context_v2": row.context_v2,
            "language": language_code,
            "generator_model": args.model,
            "generator_provider": args.provider,
            "api_base_url": args.base_url,
            "started_at": started.isoformat(),
        }
        try:
            events = _request_story(
                base_url=args.base_url,
                api_key=api_key,
                payload=payload,
                timeout=args.timeout,
            )
            final_event = next((event for event in reversed(events) if event.event == "WORKFLOW::SELESAI"), None)
            error_event = next((event for event in reversed(events) if event.event == "WORKFLOW::GALAT"), None)
            final_data = final_event.data if final_event else {}
            result.update(
                {
                    "status": "error" if error_event else ("completed" if final_event else "incomplete"),
                    "job_id": final_data.get("job_id") or next((event.data.get("job_id") for event in events if event.data.get("job_id")), ""),
                    "trace_id": final_data.get("trace_id") or final_data.get("langfuse_trace_id", ""),
                    "final_story": final_data.get("final_story", ""),
                    "quality_score": final_data.get("quality_score"),
                    "revision_count": final_data.get("revision_count"),
                    "sse_events": [event.event for event in events],
                    "api_error": error_event.data if error_event else None,
                }
            )
            if result["status"] == "completed":
                from evaluation.external_evaluator_gate import run_external_evaluator_gate

                evaluator_ids = run_external_evaluator_gate(
                    trace_id=result["trace_id"],
                    config_path=Path(args.external_evaluator_config),
                    workspace_root=ROOT,
                    output_dir=out_dir,
                )
                result["external_evaluator_ids"] = list(evaluator_ids)
                result["external_evaluation_status"] = "completed"
        except Exception as exc:
            result.update({"status": "error", "error": repr(exc)})
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        _append_checkpoint(checkpoint_path, result)
        results.append(result)
        if result.get("status") == "completed" and result.get("external_evaluation_status") == "completed":
            done.add((item_idx, language_code))
        (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--out", required=True, help="Per-model checkpoint directory")
    parser.add_argument("--model", required=True, help="Model ID accepted by the workflow API")
    parser.add_argument("--provider", default="openrouter", help="Provider label stored in run metadata")
    parser.add_argument("--base-url", default=os.getenv("BENCHMARK_API_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--api-key", default="")
    parser.add_argument("--languages", default="id,en", help="Comma-separated dataset languages")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0, help="Dataset item limit; 0 means all")
    parser.add_argument("--target-age", default="15-18")
    parser.add_argument("--story-length", default="medium")
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument(
        "--external-evaluator-config",
        default=str(ROOT / "configs" / "external_evaluators_3_models.json"),
        help="Three-evaluator config required before a completed batch item is checkpointed.",
    )
    return parser


def main() -> int:
    return run(build_argument_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
