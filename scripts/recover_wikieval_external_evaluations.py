#!/usr/bin/env python3
"""Attach mandatory three-model external evaluations to generated WikiEval stories."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"checkpoint does not exist: {path}")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def select_recovery_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select generated stories that have no completed external evaluator gate."""
    return [
        row
        for row in rows
        if row.get("final_story")
        and row.get("trace_id")
        and row.get("external_evaluation_status") != "completed"
    ]


def remove_generation_failures(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove only checkpoint rows for which no final story was generated."""
    materialized = list(rows)
    kept = [row for row in materialized if row.get("final_story")]
    return kept, len(materialized) - len(kept)


def write_results(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    jsonl_path = out_dir / "results.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out_dir / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def recover(out_dir: Path, config_path: Path) -> tuple[int, int]:
    from evaluation.external_evaluator_gate import evaluator_ids_from_config, run_external_evaluator_gate

    evaluator_ids_from_config(config_path)
    checkpoint = out_dir / "results.jsonl"
    rows = load_results(checkpoint)
    selected_ids = {id(row) for row in select_recovery_rows(rows)}
    artifact_root = out_dir / f"external_evaluator_recovery_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    recovered = 0
    failed = 0

    for row in rows:
        if id(row) not in selected_ids:
            continue
        trace_id = str(row["trace_id"])
        try:
            evaluator_ids = run_external_evaluator_gate(
                trace_id=trace_id,
                config_path=config_path,
                workspace_root=ROOT,
                output_dir=out_dir,
                artifact_root=artifact_root,
            )
        except Exception:
            failed += 1
            row["external_evaluation_status"] = "failed"
            row["external_evaluation_error"] = traceback.format_exc()
        else:
            prior_error = row.pop("error", None)
            if prior_error:
                row["external_evaluation_previous_error"] = prior_error
            row["external_evaluator_ids"] = list(evaluator_ids)
            row["external_evaluation_status"] = "completed"
            row["external_evaluation_recovered_at"] = datetime.now(timezone.utc).isoformat()
            row.pop("external_evaluation_error", None)
            recovered += 1
        write_results(out_dir, rows)
    return recovered, failed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="Existing WikiEval worker output directory")
    parser.add_argument(
        "--drop-generation-failures",
        action="store_true",
        help="Remove checkpoint rows without final_story before recovering external evaluations.",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Exit after checkpoint cleanup; requires --drop-generation-failures.",
    )
    parser.add_argument(
        "--external-evaluator-config",
        type=Path,
        default=ROOT / "configs" / "external_evaluators_3_models.json",
    )
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    if args.cleanup_only and not args.drop_generation_failures:
        raise ValueError("--cleanup-only requires --drop-generation-failures")
    if args.drop_generation_failures:
        existing = load_results(args.out / "results.jsonl")
        kept, removed = remove_generation_failures(existing)
        write_results(args.out, kept)
        print(f"removed generation-failure checkpoints: {removed}")
    if args.cleanup_only:
        return 0
    recovered, failed = recover(args.out, args.external_evaluator_config)
    print(f"external evaluation recovery: recovered={recovered} failed={failed}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
