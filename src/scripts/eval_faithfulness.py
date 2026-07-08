"""
Post-hoc Faithfulness Evaluation via Langfuse.

CLI script for running faithfulness evaluation against traces already
stored in Langfuse, or against a ground truth dataset.

Subcommands:
  trace    -- Evaluate existing Langfuse traces
  dataset  -- Upload ground truth dataset or evaluate against it

Usage:
  # Evaluate all STORM traces from last 7 days
  python -m scripts.eval_faithfulness trace \\
      --workflow storm --mode full_sentence --days 7

  # Evaluate a specific trace
  python -m scripts.eval_faithfulness trace \\
      --trace-id abc123 --mode citation_only

  # Upload ground truth dataset
  python -m scripts.eval_faithfulness dataset upload \\
      --file data/ground_truth.json --dataset-name faithfulness_v1

  # Evaluate dataset items
  python -m scripts.eval_faithfulness dataset evaluate \\
      --dataset-name faithfulness_v1 --run-name storm_v1 \\
      --workflow storm --mode full_sentence
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from scripts.trace_extractor import (
    TraceData,
    extract_trace_data,
)
from workflows.evaluator.faithfulness import (
    EvaluationMode,
    FaithfulnessEvaluator,
    FaithfulnessResult,
)


# Langfuse trace name mapping
WORKFLOW_TO_TRACE_NAME = {
    "storm": "StormWorkflow",
    "multi_agent": "StoryGenerationWorkflow",
    "single_agent": "SingleAgentWorkflow",
    "debate": "DebateWorkflow",
    "blackboard": "BlackboardWorkflow",
}


# ---------------------------------------------------------------------------
# Score writing
# ---------------------------------------------------------------------------

def _build_score_comment(result: FaithfulnessResult) -> str:
    """Build a human-readable comment for the Langfuse score."""
    lines = [
        f"Mode: {result.mode}",
        f"Sentences evaluated: {result.num_sentences}",
        f"Supported: {result.num_supported} / Unsupported: {result.num_unsupported}",
        f"Threshold: {result.threshold}",
    ]

    # Show worst-scoring sentences
    if result.sentences:
        worst = sorted(result.sentences, key=lambda s: s.score)[:3]
        if worst:
            lines.append("Lowest scoring:")
            for s in worst:
                lines.append(f"  [{s.index}] score={s.score:.3f}: {s.text[:80]}")

    return "\n".join(lines)


def _build_score_metadata(
    result: FaithfulnessResult,
    evaluator: FaithfulnessEvaluator,
    device: str,
) -> Dict[str, Any]:
    """Build metadata dict for the Langfuse score."""
    meta: Dict[str, Any] = {
        "evaluation_mode": result.mode,
        "num_sentences": result.num_sentences,
        "num_supported": result.num_supported,
        "num_unsupported": result.num_unsupported,
        "threshold": result.threshold,
        "device": device,
        "evaluator_version": evaluator.version,
    }

    # Include lowest-scoring sentences
    if result.sentences:
        worst = sorted(result.sentences, key=lambda s: s.score)[:5]
        meta["lowest_scoring_sentences"] = [
            {"index": s.index, "text": s.text[:120], "score": s.score}
            for s in worst
        ]

    return meta


def _score_name_for_mode(mode: str) -> str:
    """Return the Langfuse score name for the given evaluation mode."""
    return f"faithfulness_{mode}"


def write_score_to_langfuse(
    langfuse_client: Any,
    trace_id: str,
    result: FaithfulnessResult,
    evaluator: FaithfulnessEvaluator,
    device: str,
    score_name_override: Optional[str] = None,
) -> None:
    """Write a FaithfulnessResult as a score to Langfuse."""
    score_name = score_name_override or _score_name_for_mode(result.mode)
    comment = _build_score_comment(result)
    metadata = _build_score_metadata(result, evaluator, device)

    langfuse_client.api.scores.create(
        trace_id=trace_id,
        name=score_name,
        value=result.score,
        data_type="NUMERIC",
        comment=comment,
        metadata=metadata,
    )
    logger.info(
        f"[EVAL] Score written: trace={trace_id[:12]}... "
        f"name={score_name} value={result.score:.4f}"
    )


# ---------------------------------------------------------------------------
# Subcommand: trace
# ---------------------------------------------------------------------------

async def _evaluate_single_trace(
    trace_data: TraceData,
    evaluator: FaithfulnessEvaluator,
    ground_truth_ref: Optional[str] = None,
) -> Optional[FaithfulnessResult]:
    """Evaluate a single trace and return the result."""
    if not trace_data.output:
        logger.warning(
            f"[EVAL] Trace {trace_data.trace_id}: empty output, skipping."
        )
        return None

    # Determine contexts
    contexts = trace_data.contexts
    if not contexts and ground_truth_ref:
        # Use ground truth as fallback context (e.g., for Debate)
        contexts = [ground_truth_ref]
    elif not contexts:
        logger.warning(
            f"[EVAL] Trace {trace_data.trace_id} ({trace_data.workflow}): "
            "no contexts available and no ground truth provided, skipping."
        )
        return None

    return await evaluator.evaluate(
        user_input=trace_data.prompt,
        response=trace_data.output,
        retrieved_contexts=contexts,
    )


def _get_langfuse_client():
    """Initialize and return the Langfuse SDK client."""
    try:
        from langfuse import Langfuse
        return Langfuse()
    except ImportError:
        logger.error("Langfuse SDK not installed. Run: uv pip install langfuse")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Failed to initialize Langfuse client: {exc}")
        sys.exit(1)


def _fetch_traces(
    langfuse_client: Any,
    workflow: str,
    days: int = 7,
    limit: int = 100,
) -> list:
    """Fetch traces from Langfuse filtered by workflow name and date range."""
    trace_name = WORKFLOW_TO_TRACE_NAME.get(workflow)
    if not trace_name:
        logger.error(f"Unknown workflow: {workflow}")
        return []

    from_timestamp = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        result = langfuse_client.api.trace.list(
            limit=limit,
            from_timestamp=from_timestamp,
            filter=[
                {
                    "column": "name",
                    "operator": "equals",
                    "value": trace_name,
                }
            ],
        )
        traces = result.data if hasattr(result, "data") else result
        logger.info(
            f"[EVAL] Fetched {len(traces)} traces "
            f"(workflow={workflow}, days={days})"
        )
        return traces
    except Exception as exc:
        logger.error(f"Failed to fetch traces: {exc}")
        return []


async def cmd_trace(args: argparse.Namespace) -> None:
    """Execute the 'trace' subcommand."""
    mode = EvaluationMode(args.mode)
    evaluator = FaithfulnessEvaluator(
        mode=mode,
        device=args.device,
        batch_size=args.batch_size,
        threshold=args.threshold,
    )

    langfuse = _get_langfuse_client()

    # Fetch traces
    if args.trace_id:
        # Single trace
        try:
            trace = langfuse.api.trace.get(trace_id=args.trace_id)
            traces = [trace]
        except Exception as exc:
            logger.error(f"Failed to fetch trace {args.trace_id}: {exc}")
            return
    else:
        if not args.workflow:
            logger.error("--workflow is required when --trace-id is not set")
            return
        traces = _fetch_traces(
            langfuse, args.workflow, days=args.days, limit=args.limit
        )

    if not traces:
        logger.warning("[EVAL] No traces found.")
        return

    # Evaluate each trace
    results_summary = []
    for trace in traces:
        trace_data = extract_trace_data(trace)

        result = await _evaluate_single_trace(trace_data, evaluator)
        if result is None:
            continue

        # Write score to Langfuse
        try:
            write_score_to_langfuse(
                langfuse, trace_data.trace_id, result, evaluator, args.device
            )
        except Exception as exc:
            logger.error(
                f"Failed to write score for trace {trace_data.trace_id}: {exc}"
            )

        results_summary.append({
            "trace_id": trace_data.trace_id,
            "workflow": trace_data.workflow,
            "score": result.score,
            "passed": result.passed,
            "num_sentences": result.num_sentences,
            "num_supported": result.num_supported,
        })

    # Also write supported ratio score
    for trace, summary in zip(traces, results_summary):
        trace_data = extract_trace_data(trace)
        n = summary["num_sentences"]
        ratio = summary["num_supported"] / n if n > 0 else 0.0
        try:
            langfuse.api.scores.create(
                trace_id=trace_data.trace_id,
                name="faithfulness_supported_ratio",
                value=round(ratio, 4),
                data_type="NUMERIC",
                comment=f"Supported {summary['num_supported']}/{n}",
            )
        except Exception as exc:
            logger.warning(f"Failed to write supported_ratio score: {exc}")

    langfuse.flush()

    # Print summary
    _print_summary(results_summary, mode.value)


# ---------------------------------------------------------------------------
# Subcommand: dataset upload
# ---------------------------------------------------------------------------

def cmd_dataset_upload(args: argparse.Namespace) -> None:
    """Upload a ground truth JSON file as a Langfuse dataset."""
    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        logger.error("Dataset file must contain a JSON array of items.")
        sys.exit(1)

    langfuse = _get_langfuse_client()

    # Create dataset (idempotent)
    try:
        langfuse.api.datasets.create(
            name=args.dataset_name,
            description=f"Ground truth dataset uploaded from {file_path.name}",
        )
        logger.info(f"[EVAL] Dataset '{args.dataset_name}' created/verified.")
    except Exception as exc:
        # Dataset may already exist, which is fine
        logger.info(f"[EVAL] Dataset create response: {exc}")

    # Create dataset items
    created = 0
    for item in items:
        try:
            langfuse.api.dataset_items.create(
                dataset_name=args.dataset_name,
                input={
                    "prompt": item.get("prompt", ""),
                    "workflow_mode": item.get("workflow_mode", ""),
                },
                expected_output=item.get("expected_output", ""),
                metadata={
                    "contexts": item.get("contexts", []),
                    "source_id": item.get("id", ""),
                    **item.get("metadata", {}),
                },
            )
            created += 1
        except Exception as exc:
            logger.error(f"Failed to create dataset item: {exc}")

    langfuse.flush()
    logger.info(f"[EVAL] Uploaded {created}/{len(items)} items to '{args.dataset_name}'.")


# ---------------------------------------------------------------------------
# Subcommand: dataset evaluate
# ---------------------------------------------------------------------------

async def cmd_dataset_evaluate(args: argparse.Namespace) -> None:
    """Evaluate traces against a ground truth dataset in Langfuse."""
    mode = EvaluationMode(args.mode)
    evaluator = FaithfulnessEvaluator(
        mode=mode,
        device=args.device,
        batch_size=args.batch_size,
        threshold=args.threshold,
    )

    langfuse = _get_langfuse_client()

    # Fetch dataset
    try:
        dataset = langfuse.get_dataset(args.dataset_name)
    except Exception as exc:
        logger.error(f"Failed to fetch dataset '{args.dataset_name}': {exc}")
        return

    if not dataset.items:
        logger.warning(f"[EVAL] Dataset '{args.dataset_name}' has no items.")
        return

    # Optionally filter by workflow
    items = dataset.items
    if args.workflow:
        items = [
            item for item in items
            if (item.input or {}).get("workflow_mode") == args.workflow
        ]
        logger.info(
            f"[EVAL] Filtered to {len(items)} items "
            f"with workflow_mode='{args.workflow}'"
        )

    # Fetch traces for matching
    traces_by_prompt = {}
    if args.workflow:
        traces = _fetch_traces(langfuse, args.workflow, days=args.days, limit=500)
        for t in traces:
            td = extract_trace_data(t)
            if td.prompt:
                traces_by_prompt.setdefault(td.prompt, []).append((t, td))

    results_summary = []
    for item in items:
        item_prompt = (item.input or {}).get("prompt", "")
        item_contexts = (item.metadata or {}).get("contexts", [])
        expected_output = item.expected_output or ""

        # Find matching trace
        matching_traces = traces_by_prompt.get(item_prompt, [])
        if not matching_traces:
            logger.warning(
                f"[EVAL] No matching trace for prompt: {item_prompt[:60]}..."
            )
            continue

        # Use the most recent matching trace
        trace_obj, trace_data = matching_traces[0]

        if not trace_data.output:
            logger.warning(f"[EVAL] Empty output for trace {trace_data.trace_id}")
            continue

        # Determine contexts: use item contexts if available, else trace contexts
        eval_contexts = item_contexts if item_contexts else trace_data.contexts
        if not eval_contexts:
            logger.warning(
                f"[EVAL] No contexts for trace {trace_data.trace_id}, skipping."
            )
            continue

        # 1. Faithfulness eval: output vs contexts
        result = await evaluator.evaluate(
            user_input=item_prompt,
            response=trace_data.output,
            retrieved_contexts=eval_contexts,
        )

        try:
            write_score_to_langfuse(
                langfuse, trace_data.trace_id, result, evaluator, args.device
            )
        except Exception as exc:
            logger.error(f"Failed to write faithfulness score: {exc}")

        # 2. Ground truth eval: output vs expected_output
        gt_result = None
        if expected_output:
            gt_result = await evaluator.evaluate_against_reference(
                response=trace_data.output,
                reference=expected_output,
            )
            try:
                write_score_to_langfuse(
                    langfuse,
                    trace_data.trace_id,
                    gt_result,
                    evaluator,
                    args.device,
                    score_name_override="faithfulness_vs_ground_truth",
                )
            except Exception as exc:
                logger.error(f"Failed to write ground truth score: {exc}")

        # 3. Link trace to dataset item
        try:
            item.link(trace_obj, args.run_name)
        except Exception as exc:
            logger.warning(f"Failed to link trace to dataset item: {exc}")

        results_summary.append({
            "trace_id": trace_data.trace_id,
            "workflow": trace_data.workflow,
            "prompt": item_prompt[:60],
            "score": result.score,
            "gt_score": gt_result.score if gt_result else None,
            "passed": result.passed,
            "num_sentences": result.num_sentences,
            "num_supported": result.num_supported,
        })

    langfuse.flush()

    # Print summary
    _print_summary(results_summary, mode.value, include_gt=True)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_summary(
    results: List[Dict[str, Any]],
    mode: str,
    include_gt: bool = False,
) -> None:
    """Print evaluation summary to stdout."""
    if not results:
        print("\nNo results to display.")
        return

    print(f"\n{'='*72}")
    print(f"  Faithfulness Evaluation Summary (mode={mode})")
    print(f"{'='*72}")

    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        line = (
            f"  [{status}] {r['trace_id'][:16]}... "
            f"| score={r['score']:.4f} "
            f"| supported={r['num_supported']}/{r['num_sentences']} "
            f"| workflow={r['workflow']}"
        )
        if include_gt and r.get("gt_score") is not None:
            line += f" | gt_score={r['gt_score']:.4f}"
        print(line)

    # Aggregate stats
    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores)
    pass_count = sum(1 for r in results if r.get("passed"))

    print(f"\n  Total traces: {len(results)}")
    print(f"  Average score: {avg_score:.4f}")
    print(f"  Passed: {pass_count}/{len(results)}")

    if include_gt:
        gt_scores = [r["gt_score"] for r in results if r.get("gt_score") is not None]
        if gt_scores:
            avg_gt = sum(gt_scores) / len(gt_scores)
            print(f"  Average GT score: {avg_gt:.4f}")

    print(f"{'='*72}\n")


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="eval_faithfulness",
        description="Post-hoc faithfulness evaluation via Langfuse.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- trace subcommand ----
    trace_parser = subparsers.add_parser(
        "trace",
        help="Evaluate existing Langfuse traces.",
    )
    trace_parser.add_argument(
        "--workflow",
        choices=list(WORKFLOW_TO_TRACE_NAME.keys()),
        help="Workflow type to filter traces.",
    )
    trace_parser.add_argument(
        "--trace-id",
        help="Evaluate a specific trace by ID.",
    )
    trace_parser.add_argument(
        "--mode",
        choices=["full_sentence", "citation_only"],
        default="full_sentence",
        help="Evaluation mode (default: full_sentence).",
    )
    trace_parser.add_argument(
        "--days", type=int, default=7,
        help="Fetch traces from the last N days (default: 7).",
    )
    trace_parser.add_argument(
        "--limit", type=int, default=100,
        help="Maximum number of traces to fetch (default: 100).",
    )
    trace_parser.add_argument(
        "--device", default="cpu",
        help="Device for HHEM model (default: cpu).",
    )
    trace_parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Batch size for HHEM inference (default: 10).",
    )
    trace_parser.add_argument(
        "--threshold", type=float, default=0.5,
        help="Faithfulness threshold (default: 0.5).",
    )

    # ---- dataset subcommand ----
    ds_parser = subparsers.add_parser(
        "dataset",
        help="Manage and evaluate ground truth datasets.",
    )
    ds_subparsers = ds_parser.add_subparsers(dest="ds_command", required=True)

    # dataset upload
    upload_parser = ds_subparsers.add_parser(
        "upload",
        help="Upload a ground truth JSON file as a Langfuse dataset.",
    )
    upload_parser.add_argument(
        "--file", required=True,
        help="Path to ground truth JSON file.",
    )
    upload_parser.add_argument(
        "--dataset-name", required=True,
        help="Name for the Langfuse dataset.",
    )

    # dataset evaluate
    eval_parser = ds_subparsers.add_parser(
        "evaluate",
        help="Evaluate traces against a ground truth dataset.",
    )
    eval_parser.add_argument(
        "--dataset-name", required=True,
        help="Langfuse dataset name to evaluate against.",
    )
    eval_parser.add_argument(
        "--run-name", required=True,
        help="Name for this evaluation run.",
    )
    eval_parser.add_argument(
        "--workflow",
        choices=list(WORKFLOW_TO_TRACE_NAME.keys()),
        help="Filter dataset items by workflow mode.",
    )
    eval_parser.add_argument(
        "--mode",
        choices=["full_sentence", "citation_only"],
        default="full_sentence",
        help="Evaluation mode (default: full_sentence).",
    )
    eval_parser.add_argument(
        "--days", type=int, default=30,
        help="Search traces from the last N days (default: 30).",
    )
    eval_parser.add_argument(
        "--device", default="cpu",
        help="Device for HHEM model (default: cpu).",
    )
    eval_parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Batch size for HHEM inference (default: 10).",
    )
    eval_parser.add_argument(
        "--threshold", type=float, default=0.5,
        help="Faithfulness threshold (default: 0.5).",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "trace":
        asyncio.run(cmd_trace(args))
    elif args.command == "dataset":
        if args.ds_command == "upload":
            cmd_dataset_upload(args)
        elif args.ds_command == "evaluate":
            asyncio.run(cmd_dataset_evaluate(args))


if __name__ == "__main__":
    main()
