"""
Baseline runner: WikiEval (context_v1 + context_v2 merged) for ID + EN.

Outputs:
- Local: output/baseline_wikieval/<timestamp>/results.json, results.jsonl, results.csv
- Langfuse: traces + observations exported manually (filter tag "baseline")

Baseline definition (per requirement):
- Story generation is a single model call using prompts (no planner/researcher/writer agents)
- Evaluation uses the existing CriticAgent (GEval + RAGAS + FABLES) unchanged

Prompt policy (per requirement):
- No system prompt
- Only user prompt
- Prompt is defined in this script (not loaded from .md)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from loguru import logger


ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

DATASET_PATH = ROOT / "dataset" / "wikiEval_all.json"  # JSONL
OUTPUT_ROOT = ROOT / "output" / "baseline_wikieval"

LANG_ORDER: Tuple[str, ...] = ("id", "en")
TRACE_TAGS_BASE: Tuple[str, ...] = ("baseline", "wikieval", "ctx_v1_v2_merged")


def build_story_prompt_user_only(
    *,
    lang_code: str,
    question_raw: str,
    contexts: List[str],
    target_age: str = "15-18",
    story_style: str = "educational",
) -> str:
    question = (question_raw or "").replace("Question: ", "").strip()
    context_block = "\n\n".join(contexts).strip()
    language_display = "English" if lang_code == "en" else "Indonesian"

    if lang_code == "en":
        return (
            f"Create an educational story that helps students understand: {question}\n\n"
            f"target_age: \"{target_age}\"\n"
            f"story_style: \"{story_style}\"\n"
            f"language: \"{language_display}\"\n\n"
            "Context:\n"
            f"{context_block}\n"
        )

    return (
        f"Buat cerita edukatif yang membantu siswa memahami: {question}\n\n"
        f"target_age: \"{target_age}\"\n"
        f"story_style: \"{story_style}\"\n"
        f"language: \"{language_display}\"\n\n"
        "Context:\n"
        f"{context_block}\n"
    )


@dataclass(frozen=True)
class WikiEvalItem:
    source: str
    question: str
    answer: str
    context_v1: List[str]
    context_v2: List[str]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _dedup_preserve_order(texts: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for t in texts:
        s = (t or "").strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def load_wikieval_jsonl(path: Path) -> List[WikiEvalItem]:
    items: List[WikiEvalItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            items.append(
                WikiEvalItem(
                    source=str(obj.get("source", "")),
                    question=str(obj.get("question", "")),
                    answer=str(obj.get("answer", "")),
                    context_v1=list(obj.get("context_v1", []) or []),
                    context_v2=list(obj.get("context_v2", []) or []),
                )
            )
    if not items:
        raise ValueError(f"Empty dataset: {path}")
    return items


def build_user_message(question_raw: str, lang_code: str) -> str:
    question = (question_raw or "").replace("Question: ", "").strip()
    if lang_code == "en":
        return f"Create an educational story that helps students understand: {question}"
    return f"Buat cerita edukatif yang membantu siswa memahami: {question}"


def flatten_for_csv(result: Dict[str, Any]) -> Dict[str, Any]:
    ragas = result.get("ragas_scores") or {}
    structured = result.get("structured_critique") or {}
    return {
        "item_idx": result.get("item_idx"),
        "source": result.get("source"),
        "language": result.get("language"),
        "trace_id": result.get("trace_id"),
        "session_id": result.get("session_id"),
        "duration_sec": result.get("duration_sec"),
        "error": result.get("error"),
        "quality_score": result.get("quality_score"),
        "revision_count": result.get("revision_count"),
        "ragas_answer_relevancy": ragas.get("answer_relevancy"),
        "ragas_context_relevance": ragas.get("context_relevance"),
        "ragas_faithfulness": ragas.get("faithfulness"),
        "geval_fluency_normalized": ragas.get("geval_fluency_normalized"),
        "geval_consistency_normalized": ragas.get("geval_consistency_normalized"),
        "geval_clarity_normalized": ragas.get("geval_clarity_normalized"),
        "geval_conciseness_normalized": ragas.get("geval_conciseness_normalized"),
        "geval_repetitiveness_normalized": ragas.get("geval_repetitiveness_normalized"),
        "geval_coherence_normalized": ragas.get("geval_coherence_normalized"),
        "educational_score": structured.get("educational_score"),
        "coherence_score": structured.get("coherence_score"),
    }


def save_outputs(out_dir: Path, results: List[Dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON (array)
    (out_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # JSONL
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # CSV (flattened)
    flat_rows = [flatten_for_csv(r) for r in results]
    fieldnames: List[str] = []
    if flat_rows:
        fieldnames = list(flat_rows[0].keys())
    with (out_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)


def load_checkpoint(out_dir: Path) -> Tuple[List[Dict[str, Any]], set]:
    p = out_dir / "results.jsonl"
    if not p.exists():
        return [], set()
    results: List[Dict[str, Any]] = []
    done: set = set()
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            results.append(obj)
            if not obj.get("error") and obj.get("external_evaluation_status") == "completed":
                done.add((obj.get("item_idx"), obj.get("language")))
    return results, done


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Baseline WikiEval runner (Langfuse-native)")
    parser.add_argument("--dataset", type=str, default=str(DATASET_PATH), help="WikiEval JSONL path")
    parser.add_argument("--out", type=str, default="", help="Existing output directory to resume")
    parser.add_argument("--start", type=int, default=0, help="Start item index (0-based)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of items (0 = all)")
    parser.add_argument(
        "--language",
        choices=("id", "en", "all"),
        default="all",
        help="Language selection; all produces ID and EN (default)",
    )
    parser.add_argument("--model", default="", help="Generator model override")
    parser.add_argument("--provider", default="", help="Generator provider override")
    parser.add_argument("--provider-preferences", default="", help="OpenRouter provider JSON object")
    parser.add_argument("--evaluator-model", default="", help="Independent CriticAgent model override")
    parser.add_argument("--evaluator-provider", default="", help="Independent CriticAgent provider override")
    parser.add_argument("--evaluator-provider-preferences", default="", help="Evaluator OpenRouter provider JSON")
    parser.add_argument("--evaluator-ragas-model", default="", help="Independent RAGAS model override")
    parser.add_argument(
        "--external-evaluator-config",
        default=str(ROOT / "configs" / "external_evaluators_3_models.json"),
        help="Three-evaluator gate required before a batch item is checkpointed.",
    )
    return parser


def configure_runtime(args: argparse.Namespace) -> None:
    values = {
        "LLM_MODEL": args.model,
        "LLM_PROVIDER": args.provider,
        "OPENROUTER_PROVIDER_PREFERENCES": args.provider_preferences,
        "EVALUATOR_MODEL": args.evaluator_model,
        "EVALUATOR_PROVIDER": args.evaluator_provider,
        "EVALUATOR_OPENROUTER_PROVIDER_PREFERENCES": args.evaluator_provider_preferences,
        "EVALUATOR_RAGAS_MODEL": args.evaluator_ragas_model,
    }
    for key, value in values.items():
        if value:
            os.environ[key] = value


async def run_one(
    *,
    item: WikiEvalItem,
    item_idx: int,
    lang_code: str,
    out_dir: Path,
    external_evaluator_config: Path,
) -> Dict[str, Any]:
    import importlib

    os.environ["SYSTEM_LANGUAGE"] = lang_code
    import src.settings as _settings
    importlib.reload(_settings)

    from langchain_core.messages import HumanMessage

    from src.providers.llm_factory import get_llm
    from src.workflows.story_agent.integrations.langfuse_client import get_langfuse
    from src.workflows.story_agent.agents.critic import CriticAgent

    merged_contexts = _dedup_preserve_order(list(item.context_v1) + list(item.context_v2))
    user_message = build_user_message(item.question, lang_code)

    session_id = f"baseline_item{item_idx + 1:02d}_{lang_code}"
    trace_name = "BaselineWikiEvalWorkflow"
    generator_model = os.getenv("LLM_MODEL", "") or "provider-default"
    generator_provider = os.getenv("LLM_PROVIDER", "") or "provider-default"
    tags = list(TRACE_TAGS_BASE) + [lang_code, f"generator:{generator_model}"]

    langfuse = get_langfuse()
    trace_id = ""

    start_ts = datetime.now()
    err = None
    story_text = ""
    critic_result: Dict[str, Any] = {}

    try:
        if langfuse and langfuse.enabled:
            question_clean = (item.question or "").replace("Question: ", "").strip()
            trace_wrapper = langfuse.trace(
                name=trace_name,
                user_id=f"baseline_{lang_code}",
                session_id=session_id,
                input_data={
                    "item_idx": item_idx,
                    "source": item.source,
                    "language": lang_code,
                    "question_raw": item.question,
                    "question": question_clean,
                    "user_message": user_message,
                    "context_type": "v1+v2_merged_dedup",
                    "merged_contexts": merged_contexts,
                },
                metadata={
                    "item_idx": item_idx,
                    "source": item.source,
                    "context_type": "v1+v2_merged",
                },
                tags=tags,
            )
            trace = trace_wrapper.__enter__()
            try:
                trace_id = getattr(trace, "trace_id", "") or ""
                langfuse.set_parent_trace(trace_wrapper, session_id=session_id)

                language_display = "English" if lang_code == "en" else "Indonesian"

                user_prompt = build_story_prompt_user_only(
                    lang_code=lang_code,
                    question_raw=item.question,
                    contexts=merged_contexts,
                    target_age="15-18",
                    story_style="educational",
                )

                # Store the full prompt on the trace for Langfuse UI inspection.
                try:
                    trace.update(metadata={"user_prompt": user_prompt})
                except Exception:
                    logger.debug("[BASELINE] Langfuse trace metadata update failed", exc_info=True)

                llm = get_llm()
                resp = await llm.ainvoke([HumanMessage(content=user_prompt)])
                story_text = (getattr(resp, "content", None) or "").strip()

                critic = CriticAgent()
                critic_state: Dict[str, Any] = {
                    "user_message": user_message,
                    "theme": "",
                    "learning_objectives": (item.question or "").replace("Question: ", "").strip(),
                    "target_age": "15-18",
                    "language": language_display,
                    "story_length": "",
                    "story_style": "educational",
                    "narrative_style": "",
                    "emotional_tone": "",
                    "active_writers": ["text"],
                    "draft_content": story_text,
                    "draft_title": "",
                    "critique_feedback": "",
                    "revision_count": 2,
                    "retrieved_contexts": merged_contexts,
                    "used_sources": [],
                    "web_research_details": [],
                    "story_outline": {},
                    "characters": [],
                    "moral_message": "",
                    "messages": [],
                    "session_id": session_id,
                }
                if trace_id:
                    critic_state["trace_id"] = trace_id

                critic_result = await critic.critique(critic_state)

                # Ensure Langfuse Trace has a visible output payload.
                # Without this, Langfuse UI may show Output as undefined even though scores exist.
                try:
                    trace.update(
                        output={
                            "final_story": story_text,
                            "quality_score": critic_result.get("quality_score"),
                            "revision_count": critic_result.get("revision_count", 0),
                            "ragas_scores": critic_result.get("ragas_scores", {}),
                            "structured_critique": critic_result.get("structured_critique", {}),
                        }
                    )
                except Exception:
                    logger.debug("[BASELINE] Langfuse trace output update failed", exc_info=True)
            finally:
                trace_wrapper.__exit__(None, None, None)
        else:
            language_display = "English" if lang_code == "en" else "Indonesian"
            user_prompt = build_story_prompt_user_only(
                lang_code=lang_code,
                question_raw=item.question,
                contexts=merged_contexts,
                target_age="15-18",
                story_style="educational",
            )
            llm = get_llm()
            resp = await llm.ainvoke([HumanMessage(content=user_prompt)])
            story_text = (getattr(resp, "content", None) or "").strip()

            critic = CriticAgent()
            critic_state = {
                "user_message": user_message,
                "theme": "",
                "learning_objectives": (item.question or "").replace("Question: ", "").strip(),
                "target_age": "15-18",
                "language": language_display,
                "story_length": "",
                "story_style": "educational",
                "narrative_style": "",
                "emotional_tone": "",
                "active_writers": ["text"],
                "draft_content": story_text,
                "draft_title": "",
                "critique_feedback": "",
                "revision_count": 2,
                "retrieved_contexts": merged_contexts,
                "used_sources": [],
                "web_research_details": [],
                "story_outline": {},
                "characters": [],
                "moral_message": "",
                "messages": [],
                "session_id": session_id,
            }
            if trace_id:
                critic_state["trace_id"] = trace_id
            critic_result = await critic.critique(critic_state)
    except Exception:
        err = traceback.format_exc()

    external_evaluator_ids: List[str] = []
    if not err:
        try:
            from evaluation.external_evaluator_gate import run_external_evaluator_gate

            external_evaluator_ids = list(
                run_external_evaluator_gate(
                    trace_id=trace_id,
                    config_path=external_evaluator_config,
                    workspace_root=ROOT,
                    output_dir=out_dir,
                )
            )
        except Exception:
            err = traceback.format_exc()

    end_ts = datetime.now()
    duration_sec = (end_ts - start_ts).total_seconds()

    result: Dict[str, Any] = {
        "item_idx": item_idx,
        "source": item.source,
        "question": item.question,
        "language": lang_code,
        "session_id": session_id,
        "trace_id": trace_id,
        "context_merge": "v1+v2_dedup",
        "generator_model": generator_model,
        "generator_provider": generator_provider,
        "evaluator_model": os.getenv("EVALUATOR_MODEL", "") or generator_model,
        "evaluator_provider": os.getenv("EVALUATOR_PROVIDER", "") or generator_provider,
        "ref_answer": item.answer,
        "ref_context_v1": item.context_v1,
        "ref_context_v2": item.context_v2,
        "merged_contexts": merged_contexts,
        "started_at": start_ts.isoformat(),
        "finished_at": end_ts.isoformat(),
        "duration_sec": duration_sec,
        "error": err,
        "draft_title": "",
        "final_story": story_text,
        "quality_score": critic_result.get("quality_score"),
        "critique_feedback": critic_result.get("critique_feedback", ""),
        "revision_count": critic_result.get("revision_count", 0),
        "structured_critique": critic_result.get("structured_critique", {}),
        "ragas_scores": critic_result.get("ragas_scores", {}),
        "external_evaluator_ids": external_evaluator_ids,
        "external_evaluation_status": "completed" if external_evaluator_ids else "failed",
    }

    # write per-item json (for quick inspection)
    item_path = out_dir / f"item{item_idx + 1:02d}_{lang_code}.json"
    item_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # append checkpoint jsonl
    with (out_dir / "results.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return result


async def run_all(
    out_dir: Path,
    start: int = 0,
    limit: Optional[int] = None,
    *,
    dataset_path: Path = DATASET_PATH,
    languages: Tuple[str, ...] = LANG_ORDER,
    external_evaluator_config: Path = ROOT / "configs" / "external_evaluators_3_models.json",
) -> None:
    dataset = load_wikieval_jsonl(dataset_path)
    if limit is not None:
        dataset = dataset[: start + limit]

    results, done = load_checkpoint(out_dir)

    total = len(dataset) * len(languages)
    logger.info(f"[BASELINE] Output dir: {out_dir}")
    logger.info(f"[BASELINE] Dataset items: {len(dataset)} | Languages: {list(languages)} | Total runs: {total}")
    logger.info(f"[BASELINE] Resume loaded: {len(results)} completed")

    for idx, item in enumerate(dataset):
        if idx < start:
            continue
        for lang_code in languages:
            key = (idx, lang_code)
            if key in done:
                continue

            label = f"item{idx + 1:02d}_{lang_code}"
            logger.info(f"[BASELINE] Running {label} | source={item.source}")
            res = await run_one(
                item=item,
                item_idx=idx,
                lang_code=lang_code,
                out_dir=out_dir,
                external_evaluator_config=external_evaluator_config,
            )
            results.append(res)
            if not res.get("error") and res.get("external_evaluation_status") == "completed":
                done.add(key)

            save_outputs(out_dir, results)
            logger.info(f"[BASELINE] Saved checkpoint: {label}")

            await asyncio.sleep(1.0)


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    configure_runtime(args)

    from evaluation.external_evaluator_gate import evaluator_ids_from_config

    evaluator_ids_from_config(Path(args.external_evaluator_config))

    out_dir = Path(args.out) if args.out else (OUTPUT_ROOT / _now_stamp())
    limit = None if args.limit <= 0 else args.limit
    dataset_path = Path(args.dataset)
    languages = LANG_ORDER if args.language == "all" else (args.language,)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.txt").write_text(
        "\n".join(
            [
                "Baseline WikiEval output",
                f"Dataset: {dataset_path}",
                f"Generator model: {os.getenv('LLM_MODEL', '') or 'provider default'}",
                f"Generator provider: {os.getenv('LLM_PROVIDER', '') or 'provider default'}",
                f"Languages: {', '.join(languages)}",
                "",
                "Local files:",
                "- results.json (array)",
                "- results.jsonl (checkpoint; one JSON per run)",
                "- results.csv (flattened)",
                "- itemXX_lang.json (per-run detail)",
                "",
                "Langfuse export:",
                "- Filter traces by tag: baseline",
                "- Export Traces and Observations to CSV/JSON/JSONL to match Eval_Data format",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    asyncio.run(
        run_all(
            out_dir,
            start=args.start,
            limit=limit,
            dataset_path=dataset_path,
            languages=languages,
            external_evaluator_config=Path(args.external_evaluator_config),
        )
    )


if __name__ == "__main__":
    main()
