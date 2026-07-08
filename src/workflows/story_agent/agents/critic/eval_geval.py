"""G-EVAL quality metric using DeepEval (Liu et al., 2023 — arXiv:2303.16634).

Five sub-criteria (Fluency, Consistency, Clarity, Conciseness, Repetitiveness)
are evaluated in parallel and averaged to reduce single-prompt bias.
"""
import asyncio
import json
import time
from typing import Dict, Optional

from loguru import logger

from .deepeval_llm import DEEPEVAL_AVAILABLE, CriticDeepEvalLLM
from .models import GevalSubCriteriaInput, GevalSubCriteriaOutput

if DEEPEVAL_AVAILABLE:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams, LLMTestCase


class GEvalEvaluator:
    """Runs the G-EVAL metric across 5 sub-criteria in parallel and averages the results."""

    # Sub-criteria based on DeepEval Coherence best practices (Liu et al., 2023).
    # Each is scored independently (1-5) then averaged to avoid inter-criterion bias.
    SUB_CRITERIA: Dict[str, Dict] = {
        "Fluency": {
            "criteria": (
                "Fluency (1-5) – how smoothly the text reads, focusing on grammar and syntax. "
                "An educational children's story must have:\n"
                "1. Grammatically correct sentences with natural, flowing syntax.\n"
                "2. Age-appropriate vocabulary that does not disrupt the reading rhythm.\n"
                "3. Minimal awkward phrasing, run-on sentences, or abrupt sentence fragments."
            ),
            "steps": [
                "Read the text and identify any grammatical errors or syntax issues.",
                "Evaluate how naturally the sentences flow from one to the next.",
                "Penalize awkward phrasing, fragmented sentences, or overly complex structures that hinder readability.",
                "Assign a score for fluency on a scale of 1 to 5, where 1 is the lowest and 5 is the highest based on the Evaluation Criteria.",
            ],
        },
        "Consistency": {
            "criteria": (
                "Consistency (1-5) – ensures the text maintains a uniform style and tone throughout. "
                "An educational children's story must have:\n"
                "1. A consistent narrative voice and tone from beginning to end.\n"
                "2. Uniform level of formality and writing style across all paragraphs.\n"
                "3. No unexplained shifts in perspective or storytelling approach."
            ),
            "steps": [
                "Check whether the narrative voice and tone remain consistent throughout the story.",
                "Identify any abrupt shifts in style, formality, or perspective that disrupt uniformity.",
                "Verify that the level of educational richness and detail stays uniform from start to finish.",
                "Assign a score for consistency on a scale of 1 to 5, where 1 is the lowest and 5 is the highest based on the Evaluation Criteria.",
            ],
        },
        "Clarity": {
            "criteria": (
                "Clarity (1-5) – evaluates how easily the text can be understood by the reader. "
                "An educational children's story must have:\n"
                "1. Clear, direct, and age-appropriate language.\n"
                "2. Complex ideas explained in a way that is easy to follow.\n"
                "3. No unexplained jargon or ambiguous statements that confuse the reader."
            ),
            "steps": [
                "Evaluate whether the response uses clear and direct language appropriate for the target audience.",
                "Check if the explanation avoids jargon or explains it clearly when used.",
                "Assess whether complex ideas are presented in an accessible and easy-to-follow way.",
                "Identify any vague, ambiguous, or confusing parts that reduce understanding.",
                "Assign a score for clarity on a scale of 1 to 5, where 1 is the lowest and 5 is the highest based on the Evaluation Criteria.",
            ],
        },
        "Conciseness": {
            "criteria": (
                "Conciseness (1-5) – assesses whether the text is free of unnecessary words or details. "
                "An educational children's story must have:\n"
                "1. No filler words, padding, or over-explanation that adds length without value.\n"
                "2. Each sentence and paragraph contributing meaningfully to the story or educational goal.\n"
                "3. A tight, purposeful narrative without unnecessary digressions."
            ),
            "steps": [
                "Identify sentences or passages that contain filler words or unnecessary elaboration.",
                "Check whether each paragraph contributes meaningfully to the narrative or educational objective.",
                "Penalize verbose or padded writing that dilutes the story's impact.",
                "Assign a score for conciseness on a scale of 1 to 5, where 1 is the lowest and 5 is the highest based on the Evaluation Criteria.",
            ],
        },
        "Repetitiveness": {
            "criteria": (
                "Repetitiveness (1-5, where 5 = no repetition at all) – checks for redundancy or "
                "repeated information in the text. An educational children's story must have:\n"
                "1. No unnecessarily repeated sentences, phrases, or ideas.\n"
                "2. Each educational point or narrative beat introduced only once, unless intentional for emphasis.\n"
                "3. Minimal redundant descriptions of characters, settings, or events."
            ),
            "steps": [
                "Scan the text for repeated sentences, phrases, or ideas that appear more than once without added value.",
                "Identify redundant descriptions of characters, settings, or events.",
                "Check whether any educational concept is over-explained or restated unnecessarily.",
                "Assign a score from 1 to 5, where 5 means no repetition and 1 means highly repetitive.",
            ],
        },
    }

    def __init__(self, llm, langfuse, model_name: str):
        self.llm = llm
        self.langfuse = langfuse
        self.model_name = model_name

    async def run(self, story_text: str, trace_id: str, question: str = "") -> Dict:
        """Evaluate story quality using 5 sub-criteria concurrently.

        Returns a dict with:
        - geval_coherence: averaged raw score (1-5)
        - geval_coherence_normalized: averaged normalized score (0-1)
        - geval_coherence_reason: dict of per-criterion reasons
        - geval_coherence_{name}: per-criterion raw score (1-5, no normalized suffix)
        """
        if not DEEPEVAL_AVAILABLE:
            logger.warning(
                "[KRITIK::GEVAL] Pustaka deepeval tidak tersedia, evaluasi G-EVAL dilewati."
            )
            return {
                "geval_coherence": None,
                "geval_coherence_raw": None,
                "geval_coherence_reason": "",
            }

        start_time = time.time()

        geval_span_id = None
        if self.langfuse:
            geval_span_id = self.langfuse.start_span(
                name="geval_coherence",
                input_data={
                    "metric": "geval_coherence",
                    "framework": "DeepEval GEval (sub-criteria average)",
                    "user_input": question,
                    "story_length": len(story_text),
                    "model": self.model_name,
                    "num_sub_criteria": len(self.SUB_CRITERIA),
                    # geval_coherence   = avg raw score (1-5)
                    # geval_coherence_normalized = avg normalized score (0-1)
                    "score_scale": "1-5 (raw avg) | 0-1 (normalized avg)",
                },
                metadata={"trace_id": trace_id},
            )

        # normalized scores kept internally to compute avg_normalized_score;
        # not exposed as per-criterion keys in the return dict.
        normalized_scores: Dict[str, float] = {}
        raw_scores: Dict[str, int] = {}
        reasons: Dict[str, str] = {}
        error_msg: str = ""
        avg_raw_score: Optional[float] = None        # main: 1-5 average
        avg_normalized_score: Optional[float] = None  # main: 0-1 normalized
        elapsed: float = 0.0

        try:
            test_case = LLMTestCase(input=question, actual_output=story_text)

            async def _measure_criterion(crit_name: str, crit_config: dict):
                """Measure one sub-criterion; returns (name, normalized, raw, reason)."""
                metric = GEval(
                    name=crit_name,
                    criteria=crit_config["criteria"],
                    evaluation_steps=crit_config["steps"],
                    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
                    model=CriticDeepEvalLLM(self.llm),
                )
                await metric.a_measure(test_case)
                normalized = round(metric.score, 4)
                # GEval scores are 0-1; raw 1-5 equivalent = (score × 4) + 1
                raw = int(round((normalized * 4.0) + 1.0))
                return crit_name, normalized, raw, str(metric.reason)

            criterion_results = await asyncio.gather(
                *[_measure_criterion(n, c) for n, c in self.SUB_CRITERIA.items()],
                return_exceptions=True,
            )

            for result in criterion_results:
                if isinstance(result, Exception):
                    logger.warning(f"[KRITIK::GEVAL] Sub-kriteria gagal: {result}")
                    continue
                name, normalized, raw, reason = result
                normalized_scores[name] = normalized
                raw_scores[name] = raw
                reasons[name] = reason

                if self.langfuse:
                    input_payload = GevalSubCriteriaInput(
                        metric=f"geval_{name.lower()}",
                        model=self.model_name,
                        system_prompt=question,
                        user_input=story_text,
                        criteria=self.SUB_CRITERIA[name]["criteria"],
                        steps=self.SUB_CRITERIA[name]["steps"],
                    )
                    output_payload = GevalSubCriteriaOutput(
                        score=raw,
                        normalized=normalized,
                        reason=reason,
                    )
                    self.langfuse.log_generation(
                        name=f"geval_{name.lower()}",
                        model=self.model_name,
                        input_text=input_payload.model_dump_json(indent=2),
                        output_text=output_payload.model_dump_json(indent=2),
                        metadata={
                            "metric": f"geval_{name.lower()}",
                            "raw_score": raw,
                            "normalized_score": normalized,
                            "trace_id": trace_id,
                        },
                    )

            if raw_scores:
                avg_raw_score = round(sum(raw_scores.values()) / len(raw_scores), 2)
                avg_normalized_score = round(
                    sum(normalized_scores.values()) / len(normalized_scores), 4
                )

            elapsed = time.time() - start_time
            raw_str = f"{avg_raw_score}/5" if avg_raw_score is not None else "N/A"
            norm_str = f"{avg_normalized_score:.4f}" if avg_normalized_score is not None else "N/A"
            logger.info(
                f"[KRITIK::GEVAL] Evaluasi G-EVAL selesai — "
                f"rata-rata: {raw_str}, normalized: {norm_str} ({elapsed:.1f}s)"
            )

            if self.langfuse and avg_normalized_score is not None:
                self.langfuse.create_score(
                    name="geval_coherence_normalized",
                    value=avg_normalized_score,
                    trace_id=trace_id,
                    comment=(
                        f"DeepEval G-EVAL normalized (0-1) average "
                        f"— rata-rata raw: {avg_raw_score}/5"
                    ),
                )

        except Exception as e:
            error_msg = str(e)[:100]
            elapsed = time.time() - start_time
            logger.warning(f"[KRITIK::GEVAL] Evaluasi G-EVAL gagal: {e}")
            avg_raw_score = None
            avg_normalized_score = None

        finally:
            if self.langfuse and geval_span_id:
                self.langfuse.end_span(
                    geval_span_id,
                    output_data={
                        "geval_coherence": avg_raw_score,
                        "geval_coherence_normalized": avg_normalized_score,
                        "geval_coherence_sub_scores": raw_scores,
                        "chars": {"input_chars": len(story_text)},
                        "elapsed_seconds": round(elapsed, 2),
                        "error": error_msg or None,
                    },
                )

        return {
            "geval_coherence": avg_raw_score,               # rata-rata 1-5
            "geval_coherence_normalized": avg_normalized_score,  # normalized 0-1
            "geval_coherence_reason": reasons if not error_msg else error_msg,
            **{f"geval_coherence_{k.lower()}": v for k, v in raw_scores.items()},
        }
