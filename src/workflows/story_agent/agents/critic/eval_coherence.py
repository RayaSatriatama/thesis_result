"""LLM-based narrative coherence evaluator (Logicality & Consistency)."""
import time
from typing import List, Tuple

from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage

from ...state import StoryState
from ...prompts import get_registry
from .models import (
    LLMCoherenceEvaluation,
    CoherenceIssue,
    CoherenceGenerationInput,
    CoherenceGenerationOutput,
)
from settings import LanguageConfig


class CoherenceEvaluator:
    """Evaluates narrative coherence using structured LLM output (Logicality & Consistency)."""

    def __init__(self, llm, langfuse, model_name: str):
        self.llm = llm
        self.langfuse = langfuse
        self.model_name = model_name

    async def evaluate(
        self, state: StoryState
    ) -> Tuple[str, List[CoherenceIssue], float, bool, str]:
        """Run LLM-based coherence evaluation.

        Returns:
            (feedback_text, coherence_issues, score_0_10, needs_revision, revision_reason)
        """
        issues: List[CoherenceIssue] = []
        feedback_parts: List[str] = []
        coherence_score = 10.0
        needs_revision = False
        revision_reason = "Evaluasi gagal, mengasumsikan cerita aman dari segi koherensi."

        story_content = state.get("draft_content", "")
        global_summary = state.get("global_summary", "")

        story_words = len(story_content.split())
        paragraphs = [p.strip() for p in story_content.split('\n\n') if p.strip()]
        is_en = LanguageConfig.SYSTEM_LANGUAGE == "en"

        coh_span_id = None
        coh_start = time.time()
        try:
            registry = get_registry()
            sys_prompt = registry.get("critic_coherence").format(
                global_summary=global_summary,
                current_episode=story_content,
            )

            if self.langfuse:
                coh_span_id = self.langfuse.start_span(
                    name="critic_coherence_eval",
                    input_data={
                        "story_length_words": story_words,
                        "paragraph_count": len(paragraphs),
                    },
                    metadata={"agent": "critic", "eval_type": "coherence"},
                )

            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(
                    content=(
                        "Evaluasi kelogisan dan konsistensi cerita berikut secara mendalam:"
                        f"\n\n{story_content}"
                    )
                ),
            ]
            structured_llm = self.llm.with_structured_output(LLMCoherenceEvaluation)
            result = await structured_llm.ainvoke(messages)

            if self.langfuse:
                input_payload = CoherenceGenerationInput(
                    model=self.model_name,
                    system_prompt=sys_prompt,
                    user_input=story_content,
                    global_summary=global_summary,
                    story_length_words=story_words,
                    paragraph_count=len(paragraphs),
                )
                output_payload = CoherenceGenerationOutput(
                    coherence_score=result.coherence_score,
                    needs_revision=result.needs_revision,
                    revision_reason=result.revision_reason,
                    issues_count=len(result.issues),
                    issues=[i.model_dump() for i in result.issues],
                    strengths=result.strengths,
                    summary=result.summary,
                )
                self.langfuse.log_generation(
                    name="critic_coherence_eval_llm",
                    model=self.model_name,
                    input_text=input_payload.model_dump_json(indent=2),
                    output_text=output_payload.model_dump_json(indent=2),
                    messages=[{"role": m.type, "content": m.content} for m in messages],
                    metadata={"agent": "critic", "eval_type": "coherence"},
                )

            coherence_score = result.coherence_score
            needs_revision = result.needs_revision
            revision_reason = result.revision_reason

            for llm_issue in result.issues:
                issues.append(CoherenceIssue(
                    issue_type=llm_issue.issue_type,
                    description=llm_issue.description,
                    location=llm_issue.location,
                    severity=llm_issue.severity,
                    suggestion=llm_issue.suggestion,
                ))

            header = (
                "📊 **COHERENCE EVALUATION (LLM-based):**"
                if is_en
                else "📊 **EVALUASI KOHERENSI (LLM-based):**"
            )
            story_label = "Story" if is_en else "Cerita"
            words_label = "words" if is_en else "kata"
            paras_label = "paragraphs" if is_en else "paragraf"
            score_label = "Coherence Score" if is_en else "Skor Koherensi"
            summary_label = "Summary" if is_en else "Ringkasan"
            rev_label = "Revision Status" if is_en else "Status Revisi"

            feedback_parts += [
                header,
                f"├─ {story_label}: {story_words} {words_label}, {len(paragraphs)} {paras_label}",
                f"├─ {score_label}: {coherence_score:.1f}/10",
                f"└─ {summary_label}: {result.summary}",
                f"├─ {rev_label}: {'Needs Revision' if needs_revision else 'Passes Coherence'}",
            ]
            if needs_revision:
                feedback_parts.append(f"└─ Alasan: {revision_reason}")

            if result.strengths:
                feedback_parts.append(f"\n[{'STRENGTHS' if is_en else 'KEKUATAN'}]:")
                for s in result.strengths[:3]:
                    feedback_parts.append(f"   • {s}")

            if issues:
                feedback_parts.append(f"\n[{'ISSUES' if is_en else 'MASALAH'} ({len(issues)}):]")
                for i, issue in enumerate(issues[:5], 1):
                    critical_label = "CRITICAL" if is_en else "KRITIS"
                    major_label = "MAJOR" if is_en else "PENTING"
                    severity_marker = (
                        f"[{critical_label}]" if issue.severity == "critical"
                        else f"[{major_label}]" if issue.severity == "major"
                        else "[MINOR]"
                    )
                    lokasi_label = "Location" if is_en else "Lokasi"
                    saran_label = "Suggestion" if is_en else "Saran"
                    feedback_parts.append(
                        f"{severity_marker} {i}. [{issue.issue_type.upper()}] {issue.description}"
                    )
                    if issue.location:
                        feedback_parts.append(f"   📍 {lokasi_label}: {issue.location}")
                    feedback_parts.append(f"   💡 {saran_label}: {issue.suggestion}")

            logger.info(
                f"[KRITIK::KOHERENSI] Evaluasi koherensi selesai, skor: {coherence_score:.1f}/10. "
                f"Butuh revisi: {needs_revision}."
            )

            if self.langfuse and coh_span_id:
                self.langfuse.end_span(
                    coh_span_id,
                    output_data={
                        "coherence_score": coherence_score,
                        "coherence_issues_count": len(issues),
                        "needs_revision": needs_revision,
                        "chars": {"input_chars": len(story_content)},
                        "elapsed_time_seconds": round(time.time() - coh_start, 2),
                    },
                )

        except Exception as e:
            logger.warning(
                f"[KRITIK::KOHERENSI] Evaluasi koherensi LLM gagal, menggunakan skor default. Alasan: {e}"
            )
            feedback_parts.append(
                f"⚠️ Evaluasi koherensi: menggunakan default (error: {str(e)[:50]})"
            )
            coherence_score = 10.0

            if self.langfuse and coh_span_id:
                self.langfuse.end_span(coh_span_id, level="ERROR", status_message=str(e)[:250])

        return "\n".join(feedback_parts), issues, coherence_score, needs_revision, revision_reason
