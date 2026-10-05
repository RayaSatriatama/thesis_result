"""Read-only sample extraction from exported Langfuse observations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


_SOURCE_ROOT_NAMES = {"StoryGenerationWorkflow", "BaselineWikiEvalWorkflow"}


@dataclass(frozen=True)
class FrozenFablesSample:
    source_observation_id: str
    trace_id: str
    story: str
    contexts: tuple[str, ...]
    context_origin: str
    source_evaluator_model: str
    question: str = ""
    source_root_observation_id: str = ""


@dataclass(frozen=True)
class FrozenGEvalSample:
    """A final critic trace that contains the original prompt and generated story."""

    source_observation_id: str
    trace_id: str
    question: str
    story: str
    source_evaluator_model: str
    source_root_observation_id: str = ""


@dataclass(frozen=True)
class FrozenStructuredJudgeSample:
    """A historical structured-judge request, kept verbatim for re-evaluation."""

    source_observation_id: str
    trace_id: str
    metric: str
    system_prompt: str
    story: str
    source_evaluator_model: str


def _parse_json_object(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _source_root_observation_ids(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    roots: dict[str, str] = {}
    for row in rows:
        trace_id = str(row.get("traceId") or row.get("trace_id") or "").strip()
        observation_id = str(row.get("id") or "").strip()
        parent_id = str(row.get("parentObservationId") or row.get("parent_observation_id") or "").strip()
        if trace_id and observation_id and not parent_id and row.get("name") in _SOURCE_ROOT_NAMES:
            roots[trace_id] = observation_id
    return roots


def _extract_structured_prompt_and_story(value: Any) -> tuple[str, str, str]:
    """Support both structured Langfuse payloads and exported chat message arrays."""
    payload = _parse_json_object(value)
    if payload:
        return (
            str(payload.get("system_prompt") or "").strip(),
            str(payload.get("user_input") or "").strip(),
            str(payload.get("model") or "").strip(),
        )
    messages = value
    if isinstance(value, str):
        try:
            messages = json.loads(value)
        except json.JSONDecodeError:
            messages = []
    if not isinstance(messages, list):
        return "", "", ""
    system_prompt = ""
    story = ""
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        role = str(message.get("role") or message.get("type") or "").lower()
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if role == "system" and not system_prompt:
            system_prompt = content.strip()
        elif role in {"user", "human"}:
            story = content.strip()
    return system_prompt, story, ""


def extract_fables_samples(rows: Iterable[Mapping[str, Any]]) -> list[FrozenFablesSample]:
    """Read immutable story/context pairs from FABLES verification observations."""
    materialized_rows = list(rows)
    roots_by_trace = _source_root_observation_ids(materialized_rows)
    contexts_by_trace: dict[str, tuple[str, ...]] = {}
    questions_by_trace: dict[str, str] = {}
    stories_by_trace: dict[str, tuple[str, str]] = {}
    for row in materialized_rows:
        trace_id = str(row.get("traceId") or row.get("trace_id") or "").strip()
        if row.get("name") == "critic_agent":
            payload = _parse_json_object(row.get("input"))
            story = str(payload.get("story_content") or "").strip() if payload else ""
            if trace_id and story:
                stories_by_trace[trace_id] = (story, str(row.get("model") or ""))
            continue
        if row.get("name") == "ragas_evaluation":
            payload = _parse_json_object(row.get("input"))
            question = str(payload.get("user_input") or "").strip() if payload else ""
            prefix = "Pembuatan cerita dari teks berikut: "
            if question.startswith(prefix):
                question = question.removeprefix(prefix).strip()
            if trace_id and question:
                questions_by_trace[trace_id] = question
            continue
        if row.get("name") != "ragas_context_relevance":
            continue
        payload = _parse_json_object(row.get("input"))
        raw_contexts = payload.get("contexts") if payload else None
        if not trace_id or not isinstance(raw_contexts, list):
            continue
        contexts = tuple(str(item).strip() for item in raw_contexts if str(item).strip())
        if contexts:
            contexts_by_trace[trace_id] = contexts

    samples: list[FrozenFablesSample] = []
    seen_observation_ids: set[str] = set()
    for row in materialized_rows:
        if row.get("name") != "fables_verify_all_claims":
            continue
        payload = _parse_json_object(row.get("input"))
        if not payload:
            continue
        observation_id = str(row.get("id") or "").strip()
        story = str(payload.get("user_input") or "").strip()
        raw_contexts = payload.get("contexts")
        if not observation_id or observation_id in seen_observation_ids or not story:
            continue
        trace_id = str(row.get("traceId") or row.get("trace_id") or "").strip()
        contexts = (
            tuple(str(item).strip() for item in raw_contexts if str(item).strip())
            if isinstance(raw_contexts, list)
            else ()
        )
        context_origin = "fables_verify_all_claims"
        if not contexts:
            contexts = contexts_by_trace.get(trace_id, ())
            context_origin = "ragas_context_relevance"
        if not contexts:
            continue
        seen_observation_ids.add(observation_id)
        samples.append(
            FrozenFablesSample(
                source_observation_id=observation_id,
                trace_id=trace_id,
                story=story,
                contexts=contexts,
                context_origin=context_origin,
                source_evaluator_model=str(payload.get("model") or ""),
                question=questions_by_trace.get(trace_id, ""),
                source_root_observation_id=roots_by_trace.get(trace_id, ""),
            )
        )

    sampled_trace_ids = {sample.trace_id for sample in samples}
    for row in materialized_rows:
        if row.get("name") != "fables_faithfulness":
            continue
        trace_id = str(row.get("traceId") or row.get("trace_id") or "").strip()
        observation_id = str(row.get("id") or "").strip()
        story, source_model = stories_by_trace.get(trace_id, ("", ""))
        contexts = contexts_by_trace.get(trace_id, ())
        if (
            not trace_id
            or trace_id in sampled_trace_ids
            or not observation_id
            or not story
            or not contexts
        ):
            continue
        payload = _parse_json_object(row.get("input"))
        samples.append(
            FrozenFablesSample(
                source_observation_id=observation_id,
                trace_id=trace_id,
                story=story,
                contexts=contexts,
                context_origin="ragas_context_relevance",
                source_evaluator_model=str(payload.get("model") or source_model) if payload else source_model,
                question=questions_by_trace.get(trace_id, ""),
                source_root_observation_id=roots_by_trace.get(trace_id, ""),
            )
        )
    return samples


def split_ragas_score_groups(scores: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Expose RAGAS and FABLES scores from one existing RagasEvaluator result."""
    ragas_names = {"answer_relevancy", "context_relevance"}
    return {
        "ragas": {name: value for name, value in scores.items() if name in ragas_names},
        "fables": {name: value for name, value in scores.items() if name not in ragas_names},
    }


def _load_rows(observations_dir: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for path in sorted(observations_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
                if isinstance(value, Mapping):
                    rows.append(value)
    return rows


def load_fables_samples(observations_dir: Path) -> list[FrozenFablesSample]:
    """Load all JSONL exports without modifying them."""
    return extract_fables_samples(_load_rows(observations_dir))


def extract_geval_samples(rows: Iterable[Mapping[str, Any]]) -> list[FrozenGEvalSample]:
    """Read final critic inputs that were previously evaluated by G-Eval."""
    materialized_rows = list(rows)
    roots_by_trace = _source_root_observation_ids(materialized_rows)
    fallback_questions: dict[str, str] = {}
    fallback_stories: dict[str, tuple[str, str]] = {}
    for row in materialized_rows:
        trace_id = str(row.get("traceId") or row.get("trace_id") or "").strip()
        payload = _parse_json_object(row.get("input"))
        if not trace_id or not payload:
            continue
        if row.get("name") in {"ragas_evaluation", "ragas_context_relevance"}:
            question = str(payload.get("user_input") or "").strip()
            prefix = "Pembuatan cerita dari teks berikut: "
            if question.startswith(prefix):
                question = question.removeprefix(prefix).strip()
            if question:
                fallback_questions[trace_id] = question
        elif row.get("name") == "fables_verify_all_claims":
            story = str(payload.get("user_input") or "").strip()
            if story:
                fallback_stories[trace_id] = (story, str(payload.get("model") or ""))
    samples: list[FrozenGEvalSample] = []
    seen_observation_ids: set[str] = set()
    for row in materialized_rows:
        if row.get("name") != "critic_agent":
            continue
        observation_id = str(row.get("id") or "").strip()
        input_payload = _parse_json_object(row.get("input"))
        output_payload = _parse_json_object(row.get("output"))
        ragas_scores = output_payload.get("ragas_scores") if output_payload else None
        trace_id = str(row.get("traceId") or row.get("trace_id") or "").strip()
        question = str(input_payload.get("user_message") or "").strip() if input_payload else ""
        story = str(input_payload.get("story_content") or "").strip() if input_payload else ""
        fallback_story, fallback_model = fallback_stories.get(trace_id, ("", ""))
        question = question or fallback_questions.get(trace_id, "")
        story = story or fallback_story
        if (
            not observation_id
            or observation_id in seen_observation_ids
            or not question
            or not story
            or not isinstance(ragas_scores, Mapping)
            or "geval_coherence" not in ragas_scores
        ):
            continue
        seen_observation_ids.add(observation_id)
        samples.append(
            FrozenGEvalSample(
                source_observation_id=observation_id,
                trace_id=trace_id,
                question=question,
                story=story,
                source_evaluator_model=str(row.get("model") or fallback_model),
                source_root_observation_id=roots_by_trace.get(trace_id, ""),
            )
        )
    return samples


def load_geval_samples(observations_dir: Path) -> list[FrozenGEvalSample]:
    """Load final G-Eval-ready stories from exported observations without writes."""
    return extract_geval_samples(_load_rows(observations_dir))


_STRUCTURED_JUDGE_OBSERVATIONS = {
    "educational": "critic_educational_eval_llm",
    "coherence": "critic_coherence_eval_llm",
}


def extract_structured_judge_samples(
    rows: Iterable[Mapping[str, Any]], metric: str
) -> list[FrozenStructuredJudgeSample]:
    """Load saved system prompts and stories for one historical judge metric."""
    observation_name = _STRUCTURED_JUDGE_OBSERVATIONS.get(metric)
    if not observation_name:
        raise ValueError(f"unsupported structured judge metric: {metric}")
    samples: list[FrozenStructuredJudgeSample] = []
    seen_observation_ids: set[str] = set()
    for row in rows:
        if row.get("name") != observation_name:
            continue
        observation_id = str(row.get("id") or "").strip()
        system_prompt, story, payload_model = _extract_structured_prompt_and_story(row.get("input"))
        if not observation_id or observation_id in seen_observation_ids or not system_prompt or not story:
            continue
        seen_observation_ids.add(observation_id)
        samples.append(
            FrozenStructuredJudgeSample(
                source_observation_id=observation_id,
                trace_id=str(row.get("traceId") or row.get("trace_id") or ""),
                metric=metric,
                system_prompt=system_prompt,
                story=story,
                source_evaluator_model=payload_model or str(row.get("model") or ""),
            )
        )
    return samples


def load_structured_judge_samples(
    observations_dir: Path, metric: str
) -> list[FrozenStructuredJudgeSample]:
    """Load one historical structured judge metric from exported JSONL files."""
    return extract_structured_judge_samples(_load_rows(observations_dir), metric)
