"""Educational quality evaluator for the Critic Agent."""
import time
from typing import List, Tuple

from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage

from ...state import StoryState
from ...prompts import get_registry
from ...utils.retry import invoke_with_retry
from .models import (
    EducationalGenerationInput,
    LLMEducationalEvaluation,
)


class EducationalEvaluator:
    """Evaluates the educational quality and alignment of a generated story."""

    def __init__(self, llm, langfuse, model_name: str):
        self.llm = llm
        self.langfuse = langfuse
        self.model_name = model_name

    async def evaluate(
        self, state: StoryState, active_writers: list = None
    ) -> LLMEducationalEvaluation:
        """Run educational quality evaluation using structured LLM output.

        Returns an LLMEducationalEvaluation Pydantic object — score is always present.
        """
        if active_writers is None:
            active_writers = ["text"]

        story = state.get("draft_content", "")
        target_age = state.get("target_age", "unknown")
        user_prompt = state.get("user_message", "")
        theme = state.get("theme", "")
        story_style = state.get("story_style", "")
        story_length = state.get("story_length", "medium")

        diagram_active = "ACTIVE" if "diagram" in active_writers else "INACTIVE"
        image_active = "ACTIVE" if "image" in active_writers else "INACTIVE"

        registry = get_registry()
        sys_prompt = registry.get("critic").format(
            target_age=target_age,
            theme=theme,
            user_prompt=user_prompt,
            story_style=story_style,
            story_length=story_length,
            diagram_active=diagram_active,
            image_active=image_active,
        )

        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Evaluate this story:\n\n{story}"),
        ]
        structured_messages = [{"role": m.type, "content": m.content} for m in messages]

        edu_span_id = None
        edu_start = time.time()
        if self.langfuse:
            edu_span_id = self.langfuse.start_span(
                name="critic_educational_eval",
                input_data={
                    "target_age": target_age,
                    "theme": theme,
                    "story_style": story_style,
                    "story_length_setting": story_length,
                    "active_writers": active_writers,
                },
                metadata={"agent": "critic", "eval_type": "educational"},
            )

        result: LLMEducationalEvaluation = None
        try:
            edu_llm = self.llm.with_structured_output(LLMEducationalEvaluation)
            result = await invoke_with_retry(
                edu_llm,
                messages,
                max_retries=3,
                base_delay=3.0,
                max_delay=30.0,
            )

            if self.langfuse:
                input_payload = EducationalGenerationInput(
                    model=self.model_name,
                    system_prompt=sys_prompt,
                    user_input=story,
                    target_age=target_age,
                    theme=theme,
                    story_style=story_style,
                    story_length=story_length,
                    active_writers=active_writers,
                )
                self.langfuse.log_generation(
                    name="critic_educational_eval_llm",
                    model=self.model_name,
                    input_text=input_payload.model_dump_json(indent=2),
                    output_text=result.model_dump_json(indent=2),
                    messages=structured_messages,
                    metadata={"agent": "critic", "eval_type": "educational"},
                )

            return result

        finally:
            if self.langfuse and edu_span_id:
                edu_score_val = result.score if result else None
                self.langfuse.end_span(
                    edu_span_id,
                    output_data={
                        "educational_score": edu_score_val,
                        "chars": {"output_chars": len(result.feedback) if result else 0},
                        "elapsed_seconds": round(time.time() - edu_start, 2),
                    },
                )

    @staticmethod
    def fallback_result() -> LLMEducationalEvaluation:
        """Return a safe default when evaluation fails (e.g. exception in gather)."""
        return LLMEducationalEvaluation(
            theme_relevance_score=3,
            age_appropriateness_score=3,
            narrative_engagement_score=3,
            educational_value_score=3,
            instruction_alignment_score=3,
            score=3.0,
            gap_analysis="Sufficient",
            decision="REVISE",
            needs_revision=True,
            feedback="Evaluasi gagal, menggunakan nilai default.",
            strengths=[],
            weaknesses=[],
        )
