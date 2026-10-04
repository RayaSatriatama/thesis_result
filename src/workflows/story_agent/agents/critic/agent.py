"""
CriticAgent — orchestrates educational, coherence, G-EVAL, and RAGAS/FABLES evaluation.

Produces structured critique for targeted paragraph-level revisions.
Supports 429 Rate Limit retry via invoke_with_retry.
"""
import re
import time
import asyncio
from typing import List, Dict, Any, Optional

from loguru import logger

from ...state import StoryState
from ...story_canvas import StructuredCritique, ParagraphIssue
from .models import CoherenceIssue, LLMEducationalEvaluation
from .eval_educational import EducationalEvaluator
from .eval_coherence import CoherenceEvaluator
from .eval_geval import GEvalEvaluator
from .eval_ragas import RagasEvaluator, RAGAS_AVAILABLE
from settings import EvaluatorConfig, ModelConfig, LanguageConfig, StoryConfig
from providers.llm_factory import get_llm

try:
    from ...integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None


class CriticAgent:
    """Evaluates educational effectiveness AND narrative coherence using LLM-as-a-Judge.

    Delegates evaluation work to four specialised evaluators:
    - EducationalEvaluator  — rubric-based educational quality scoring
    - CoherenceEvaluator    — LLM structured-output coherence check
    - GEvalEvaluator        — DeepEval G-EVAL (5 sub-criteria, parallel)
    - RagasEvaluator        — RAGAS + FABLES faithfulness (final-pass only)
    """

    def __init__(self, model_name: str = None, credentials=None, project=None):
        evaluator_provider = EvaluatorConfig.provider() or None
        evaluator_model = EvaluatorConfig.model()
        self.model_name = evaluator_model or model_name or ModelConfig.GEMINI_MODEL
        self._openrouter_provider_preferences = EvaluatorConfig.openrouter_provider_preferences()
        # Evaluator DeepEval (G-EVAL) & edukatif dkk default ke 0.0 (mengabaikan env)
        self.llm = get_llm(
            temperature=0.0,
            model_name=self.model_name,
            provider=evaluator_provider,
            openrouter_provider_preferences=self._openrouter_provider_preferences,
        )
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None

        self._educational_eval = EducationalEvaluator(self.llm, self.langfuse, self.model_name)
        self._coherence_eval = CoherenceEvaluator(self.llm, self.langfuse, self.model_name)
        self._geval_eval = GEvalEvaluator(self.llm, self.langfuse, self.model_name)

        # Initialize RAGAS LLM/Embeddings via OpenRouter
        ragas_llm = ragas_embeddings = ragas_openai_client = None
        ragas_model_name = "google/gemini-2.5-flash"

        if RAGAS_AVAILABLE:
            import os
            from settings import LLMProviderConfig
            from ragas.llms import llm_factory
            from ragas.embeddings import OpenAIEmbeddings
            from openai import AsyncOpenAI

            or_api_key = LLMProviderConfig.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")
            or_base_url = LLMProviderConfig.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1"
            ragas_model_name = (
                EvaluatorConfig.ragas_model()
                or (self.model_name if evaluator_provider == "openrouter" else "")
                or os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")
            )
            ragas_embed = os.environ.get("RAGAS_EMBED_MODEL", "google/gemini-embedding-001")

            if or_api_key:
                _or_llm_client = AsyncOpenAI(
                    api_key=or_api_key,
                    base_url=or_base_url,
                    default_headers={
                        "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", ""),
                        "X-Title": "RAGAS Evaluation",
                    },
                )
                _or_embed_client = AsyncOpenAI(api_key=or_api_key, base_url=or_base_url)
                ragas_llm = llm_factory(
                    ragas_model_name, provider="openai", client=_or_llm_client, max_tokens=8192, temperature=0.01
                )
                ragas_embeddings = OpenAIEmbeddings(client=_or_embed_client, model=ragas_embed)
                ragas_openai_client = _or_llm_client
                logger.info(
                    f"[KRITIK::PENGATURAN] Subsistem evaluasi RAGAS siap — "
                    f"model: {ragas_model_name}, embedding: {ragas_embed}."
                )
            else:
                logger.warning(
                    "[KRITIK::PENGATURAN] Kunci OpenRouter tidak ditemukan, "
                    "evaluasi RAGAS tidak dapat dijalankan."
                )

        self._ragas_eval = RagasEvaluator(
            ragas_llm=ragas_llm,
            embeddings=ragas_embeddings,
            openai_client=ragas_openai_client,
            model_name=ragas_model_name,
            langfuse=self.langfuse,
            openrouter_provider_preferences=self._openrouter_provider_preferences,
        )

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    async def critique(self, state: StoryState) -> dict:
        """Orchestrate all evaluations and produce a structured critique.

        Runs educational + coherence in parallel, then (on approve path) runs
        RAGAS + G-EVAL concurrently.

        Returns updated state keys: quality_score, critique_feedback,
        revision_count, current_stage, structured_critique, coherence_issues,
        research_feedback, messages, ragas_scores.
        """
        story = state.get("draft_content", "")
        revision_count = state.get("revision_count", 0)

        logger.info(
            f"[KRITIK::MEMULAI] Saya mulai memeriksa cerita ini "
            f"(revisi ke-{revision_count}, panjang: {len(story)} karakter). "
            "Evaluasi edukatif dan koherensi akan berjalan bersamaan."
        )
        start_time = time.time()

        critique_span_id = None
        if self.langfuse:
            critique_span_id = self.langfuse.start_span(
                name="critic_agent",
                input_data={
                    "user_message": state.get("user_message", ""),
                    "story_content": story,
                    "story_length": len(story),
                    "revision_count": revision_count,
                    "target_age": state.get("target_age", "unknown"),
                    "theme": state.get("theme", ""),
                    "story_style": state.get("story_style", ""),
                    "learning_objectives": state.get("learning_objectives", ""),
                    "moral_message": state.get("moral_message", ""),
                },
                metadata={"agent": "critic", "target_age": state.get("target_age", "unknown")},
            )

        coherence_feedback = ""
        coherence_issues: List[CoherenceIssue] = []
        coherence_score = 10.0

        active_writers = state.get("active_writers", ["text"])

        async def _no_coherence():
            return ("", [], 10.0, False, "No story content to evaluate.")

        results = await asyncio.gather(
            self._educational_eval.evaluate(state, active_writers),
            self._coherence_eval.evaluate(state) if story else _no_coherence(),
            return_exceptions=True,
        )

        if isinstance(results[0], Exception):
            raise results[0]
        edu_result: LLMEducationalEvaluation = results[0]

        needs_revision = False
        revision_reason = ""
        if len(results) > 1 and not isinstance(results[1], Exception):
            coherence_feedback, coherence_issues, coherence_score, needs_revision, revision_reason = results[1]
        elif isinstance(results[1], Exception):
            logger.warning(
                f"[KRITIK::KOHERENSI] Evaluasi koherensi mengalami galat: {results[1]}"
            )

        edu_score = edu_result.score
        alignment_score = float(edu_result.instruction_alignment_score)
        gap_status = edu_result.gap_analysis
        edu_strengths = edu_result.strengths
        edu_weaknesses = edu_result.weaknesses
        educational_feedback = edu_result.feedback

        overall_score = edu_score

        new_revision_count = state.get("revision_count", 0) + 1
        max_revisions = StoryConfig.MAX_REVISIONS
        quality_threshold = StoryConfig.QUALITY_THRESHOLD

        educational_passed = edu_score >= quality_threshold
        alignment_passed = alignment_score >= 4.0
        both_passed = educational_passed and alignment_passed
        research_needed = (
            edu_result.decision == "NEED_MORE_RESEARCH"
            or "Missing" in gap_status
        )

        if not alignment_passed:
            coherence_issues.insert(0, CoherenceIssue(
                issue_type="alignment",
                description=f"Story does not align with user request (Score: {alignment_score}/5).",
                location="Whole Story",
                severity="critical",
                suggestion=f"Strictly follow user request: {state.get('user_message')}",
            ))
            logger.warning(
                f"[KRITIK::VETO] Cerita belum sesuai dengan permintaan pengguna "
                f"(keselarasan: {alignment_score}/5), saya meminta revisi terarah."
            )

        # Only critical/major issues force revision — minor issues are noted but not blocking.
        # The LLM's own needs_revision flag handles the overall judgment; this is a safety net
        # for cases where severity warrants override regardless of the LLM's verdict.
        has_coherence_issues = any(
            issue.severity in ("critical", "major") for issue in coherence_issues
        )

        if both_passed and not research_needed and not needs_revision and not has_coherence_issues:
            final_decision = "APPROVE"
            next_stage = "finalize"
        elif new_revision_count >= max_revisions:
            final_decision = "APPROVE (max revisi)"
            next_stage = "finalize"
        elif research_needed and alignment_passed:
            final_decision = "NEED_MORE_RESEARCH"
            next_stage = "research"
            logger.warning(
                f"[KRITIK::GAP] Saya menemukan celah informasi dalam cerita ini: {gap_status}. "
                "Meminta riset tambahan sebelum melanjutkan."
            )
        elif needs_revision or has_coherence_issues or not alignment_passed:
            final_decision = "REVISE"
            next_stage = "writing"

            reasons = []
            if (
                needs_revision
                and revision_reason
                and revision_reason != "Evaluasi gagal, mengasumsikan cerita aman dari segi koherensi."
            ):
                reasons.append(revision_reason)
            if has_coherence_issues:
                reasons.append(f"Terdapat {len(coherence_issues)} masalah (termasuk koherensi/keselarasan)")
            if not alignment_passed and not has_coherence_issues:
                reasons.append("Cerita belum sesuai permintaan.")

            combined_reason = " | ".join(reasons) or "Diperlukan revisi."
            logger.warning(
                f"[KRITIK::REVISI] Membuka kembali tahap penulisan. Alasan: {combined_reason}"
            )
            needs_revision = True
            revision_reason = combined_reason
        else:
            final_decision = "REVISE"
            next_stage = "writing"

        revision_targets = self._build_revision_targets(coherence_issues, edu_weaknesses)
        paragraph_issues = self._convert_to_paragraph_issues(
            coherence_issues, state.get("story_canvas")
        )
        summary_feedback = self._create_summary(
            edu_score, coherence_score, coherence_issues, edu_weaknesses
        )

        structured = StructuredCritique(
            overall_score=overall_score,
            paragraph_issues=paragraph_issues,
            general_feedback=educational_feedback,
            decision=final_decision,
            educational_score=edu_score,
            coherence_score=coherence_score,
            educational_strengths=edu_strengths,
            educational_weaknesses=edu_weaknesses,
            revision_targets=revision_targets,
            summary_feedback=summary_feedback,
        )

        full_critique = self._combine_feedback_structured(
            educational_feedback, coherence_feedback, structured
        )
        structured.general_feedback = full_critique

        logger.info(
            f"[KRITIK::MENILAI] Kualitas edukatif: {edu_score:.1f}/5, "
            f"{'LULUS' if educational_passed else 'BELUM LULUS'} (ambang batas: {quality_threshold})"
        )
        logger.info(f"[KRITIK::MENILAI] Skor keseluruhan cerita: {overall_score:.1f}/5.")
        logger.info(
            f"[KRITIK::MEMUTUSKAN] Keputusan saya: {final_decision}, cerita akan "
            f"{'diteruskan ke tahap finalisasi' if next_stage == 'finalize' else 'kembali ke tahap penulisan' if next_stage == 'writing' else 'dikembalikan untuk riset tambahan'}."
        )
        if coherence_issues:
            logger.warning(
                f"[KRITIK::PERINGATAN] Saya menemukan {len(coherence_issues)} masalah koherensi "
                "dalam cerita, ini akan dijadikan panduan revisi."
            )

        # RAGAS + G-EVAL (only on final-pass stories)
        ragas_results: Dict = {}
        if StoryConfig.ENABLE_CRITIC_EVAL_METRICS and RAGAS_AVAILABLE and state.get("retrieved_contexts") and next_stage == "finalize":
            used_srcs = set(state.get("used_sources", []))
            web_details = state.get("web_research_details", [])
            raw_contexts = state.get("retrieved_contexts", [])

            if used_srcs and web_details:
                used_web_texts = [
                    d["answer"]
                    for d in web_details
                    if any(uri in used_srcs for uri in d.get("source_uris", []))
                ]
                kg_chunks = [c for c in raw_contexts if c.startswith("## KG Context")]
                ragas_contexts = used_web_texts + kg_chunks or raw_contexts
            else:
                ragas_contexts = raw_contexts

            outline = state.get("story_outline", {})
            characters = state.get("characters", [])
            moral = state.get("moral_message", "")
            theme = state.get("theme", "")
            learning_objectives = state.get("learning_objectives", "")

            if outline or characters or moral:
                char_lines = "\n".join(
                    f"  - {c.get('name', '?')} ({c.get('role', '?')}): {c.get('personality', '')}"
                    for c in characters
                ) or "  (tidak ada)"
                plan_context = (
                    f"## Rencana Cerita (Planner Output)\n"
                    f"Tema: {theme}\n"
                    f"Tujuan Pembelajaran: {learning_objectives}\n"
                    f"Pesan Moral: {moral}\n\n"
                    f"Outline:\n"
                    f"  - Pembukaan: {outline.get('introduction', '')}\n"
                    f"  - Konflik: {outline.get('conflict', '')}\n"
                    f"  - Klimaks: {outline.get('climax', '')}\n"
                    f"  - Resolusi: {outline.get('resolution', '')}\n\n"
                    f"Tokoh:\n{char_lines}"
                )
                ragas_contexts = [plan_context] + ragas_contexts

            _ragas_question = state.get("user_message", "")
            _ragas_trace_id = state.get("trace_id", "")
            _story_question = "Pembuatan cerita dari teks berikut: " + _ragas_question

            ragas_results_raw, geval_dict = await asyncio.gather(
                self._ragas_eval.run(
                    question=_ragas_question,
                    answer=story,
                    contexts=ragas_contexts,
                    trace_id=_ragas_trace_id,
                ),
                self._geval_eval.run(
                    story_text=story,
                    trace_id=_ragas_trace_id,
                    question=_story_question,
                ),
            )
            ragas_results = {**ragas_results_raw, **(geval_dict or {})}

        if self.langfuse and self.langfuse.enabled:
            try:
                trace_id = getattr(self.langfuse, "_parent_trace_id", None)
                self.langfuse.create_score(
                    name="educational_score",
                    value=edu_score,
                    trace_id=trace_id,
                    comment=f"Educational quality: {len(edu_strengths)} strengths, {len(edu_weaknesses)} weaknesses",
                    metadata={"strengths": edu_strengths[:3], "weaknesses": edu_weaknesses[:3]},
                )
                self.langfuse.create_score(
                    name="overall_score",
                    value=overall_score,
                    trace_id=trace_id,
                    comment=f"Overall quality (Final Decision: {final_decision})",
                    metadata={"decision": final_decision, "revision_count": new_revision_count},
                )
                self.langfuse.create_score(
                    name="revision_count",
                    value=new_revision_count,
                    trace_id=trace_id,
                    comment=f"Number of revision cycles completed (decision: {final_decision})",
                    metadata={"decision": final_decision},
                )
                issue_breakdown: Dict[str, int] = {}
                for issue in coherence_issues:
                    key = f"{issue.severity}_{issue.issue_type}"
                    issue_breakdown[key] = issue_breakdown.get(key, 0) + 1

                if critique_span_id:
                    elapsed_time = time.time() - start_time
                    self.langfuse.end_span(
                        span_id=critique_span_id,
                        output_data={
                            "critique_feedback": full_critique,
                            "educational_score": edu_score,
                            "overall_score": overall_score,
                            "decision": final_decision,
                            "educational_strengths": edu_strengths,
                            "educational_weaknesses": edu_weaknesses,
                            "coherence_issues_count": len(coherence_issues),
                            "issue_breakdown": issue_breakdown,
                            "revision_count": new_revision_count,
                            "next_stage": next_stage,
                            "elapsed_time_seconds": round(elapsed_time, 2),
                            "ragas_scores": ragas_results,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"[KRITIK::GALAT] Pencatatan Langfuse gagal, hasil evaluasi tidak tersimpan "
                    f"di platform observabilitas: {e}"
                )

        coherence_issues_text = [
            f"[{issue.severity.upper()}] {issue.issue_type}: {issue.description}"
            for issue in coherence_issues
        ]

        return {
            "quality_score": overall_score,
            "critique_feedback": full_critique,
            "revision_count": new_revision_count,
            "current_stage": next_stage,
            "structured_critique": (
                structured.to_dict() if hasattr(structured, "to_dict") else structured
            ),
            "coherence_issues": coherence_issues_text,
            "research_feedback": gap_status if final_decision == "NEED_MORE_RESEARCH" else "",
            "messages": [{"role": "critic", "content": full_critique}],
            "ragas_scores": ragas_results,
        }

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _build_revision_targets(
        self, coherence_issues: List[CoherenceIssue], edu_weaknesses: List[str]
    ) -> List[Dict]:
        """Build prioritised revision targets from coherence issues and educational weaknesses."""
        targets = []

        for issue in coherence_issues:
            targets.append({
                "source": "coherence",
                "type": issue.issue_type,
                "location": issue.location,
                "issue": issue.description,
                "suggestion": issue.suggestion,
                "severity": issue.severity,
            })

        sys_lang = LanguageConfig.SYSTEM_LANGUAGE
        suggestion_prefix = "Fix:" if sys_lang == "en" else "Perbaiki:"

        for weakness in edu_weaknesses:
            targets.append({
                "source": "educational",
                "type": "content",
                "location": "general",
                "issue": weakness,
                "suggestion": f"{suggestion_prefix} {weakness}",
                "severity": "minor",
            })

        severity_order = {"critical": 0, "major": 1, "minor": 2}
        targets.sort(key=lambda x: severity_order.get(x.get("severity", "minor"), 2))
        return targets

    def _convert_to_paragraph_issues(
        self,
        coherence_issues: List[CoherenceIssue],
        canvas_data: Optional[Dict],
    ) -> List[ParagraphIssue]:
        """Convert CoherenceIssues to ParagraphIssues, mapping to canvas paragraphs when possible."""
        paragraph_issues = []
        paragraphs = []
        if canvas_data and isinstance(canvas_data, dict):
            paragraphs = canvas_data.get("paragraphs", [])

        for issue in coherence_issues:
            para_idx = -1
            para_id = ""

            loc_match = re.search(r'[Pp]aragraf?\s*(\d+)', issue.location)
            if loc_match:
                para_idx = int(loc_match.group(1)) - 1
                if paragraphs and 0 <= para_idx < len(paragraphs):
                    para_id = paragraphs[para_idx].get("id", f"p_{para_idx}")

            if para_idx < 0 and paragraphs:
                search_terms = self._extract_search_terms(issue.description)
                for i, para in enumerate(paragraphs):
                    content = para.get("content", "").lower()
                    if any(term.lower() in content for term in search_terms):
                        para_idx = i
                        para_id = para.get("id", f"p_{i}")
                        break

            paragraph_issues.append(ParagraphIssue(
                paragraph_index=para_idx,
                paragraph_id=para_id or f"unknown_{len(paragraph_issues)}",
                issue_type=issue.issue_type,
                description=issue.description,
                suggested_fix=issue.suggestion,
                severity=issue.severity,
                location=issue.location,
            ))

        return paragraph_issues

    def _extract_search_terms(self, description: str) -> List[str]:
        """Extract searchable keywords from an issue description."""
        terms = re.findall(r"'([^']+)'", description)
        caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', description)
        terms.extend(caps)
        return terms[:5]

    def _create_summary(
        self,
        edu_score: float,
        coh_score: float,
        coherence_issues: List[CoherenceIssue],
        weaknesses: List[str],
    ) -> str:
        """Create a human-readable evaluation summary."""
        from settings import StoryConfig
        threshold = StoryConfig.QUALITY_THRESHOLD
        is_en = LanguageConfig.SYSTEM_LANGUAGE == "en"

        edu_passed = edu_score >= threshold
        coh_passed = coh_score >= threshold
        parts = []

        if edu_passed and coh_passed:
            parts.append(
                "[OK] High quality story! Both aspects met standards."
                if is_en
                else "[OK] Cerita berkualitas tinggi! Kedua aspek memenuhi standar."
            )
        elif edu_passed and not coh_passed:
            parts.append(
                f"[WARN] Narrative coherence needs improvement (score: {coh_score:.1f}, threshold: {threshold})."
                if is_en
                else f"[WARN] Koherensi naratif perlu perbaikan (skor: {coh_score:.1f}, threshold: {threshold})."
            )
        elif coh_passed and not edu_passed:
            parts.append(
                f"[WARN] Educational quality needs improvement (score: {edu_score:.1f}, threshold: {threshold})."
                if is_en
                else f"[WARN] Kualitas edukatif perlu perbaikan (skor: {edu_score:.1f}, threshold: {threshold})."
            )
        else:
            parts.append(
                "[WARN] Both aspects (educational and coherence) need significant improvement."
                if is_en
                else "[WARN] Kedua aspek (edukatif dan koherensi) perlu perbaikan signifikan."
            )

        critical_issues = [i for i in coherence_issues if i.severity == "critical"]
        if critical_issues:
            parts.append(
                f"\n[CRITICAL] {len(critical_issues)} critical issues that must be fixed:"
                if is_en
                else f"\n[CRITICAL] {len(critical_issues)} masalah kritis yang harus diperbaiki:"
            )
            for issue in critical_issues[:3]:
                parts.append(f"   - {issue.description}")

        return "\n".join(parts)

    def _combine_feedback_structured(
        self,
        educational: str,
        coherence: str,
        structured: StructuredCritique,
    ) -> str:
        """Combine all feedback into a concise formatted output string."""
        from settings import StoryConfig
        threshold = StoryConfig.QUALITY_THRESHOLD
        is_en = LanguageConfig.SYSTEM_LANGUAGE == "en"

        edu_passed = structured.educational_score >= threshold
        coh_passed = structured.coherence_score >= threshold

        edu_status = ("PASS" if edu_passed else "FAIL") if is_en else ("LULUS" if edu_passed else "GAGAL")
        coh_status = ("PASS" if coh_passed else "FAIL") if is_en else ("LULUS" if coh_passed else "GAGAL")
        eval_label = "EVALUATION" if is_en else "EVALUASI"

        return (
            f"[{eval_label}] Edu={structured.educational_score:.1f}/10 ({edu_status}) "
            f"| Coh={structured.coherence_score:.1f}/10 ({coh_status}) "
            f"| {structured.decision}\n"
            f"{structured.summary_feedback}"
        )
