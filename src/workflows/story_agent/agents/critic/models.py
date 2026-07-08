"""Data models for the Critic Agent evaluation pipeline."""
from dataclasses import dataclass, asdict
from typing import List, Optional

from pydantic import BaseModel, Field
from settings import LanguageConfig


# ── Langfuse generation logging models ────────────────────────────────────────

class CoherenceGenerationInput(BaseModel):
    """Structured input payload logged to Langfuse for critic_coherence_eval_llm."""
    metric: str = "critic_coherence_eval_llm"
    model: str
    system_prompt: str
    user_input: str
    global_summary: str
    story_length_words: int
    paragraph_count: int


class CoherenceGenerationOutput(BaseModel):
    """Structured output payload logged to Langfuse for critic_coherence_eval_llm."""
    coherence_score: float
    needs_revision: bool
    revision_reason: str
    issues_count: int
    issues: list
    strengths: list
    summary: str


class EducationalGenerationInput(BaseModel):
    """Structured input payload logged to Langfuse for critic_educational_eval_llm."""
    metric: str = "critic_educational_eval_llm"
    model: str
    system_prompt: str
    user_input: str
    target_age: str
    theme: str
    story_style: str
    story_length: str
    active_writers: list


class EducationalGenerationOutput(BaseModel):
    """Structured output payload logged to Langfuse for critic_educational_eval_llm."""
    score: float
    instruction_alignment_score: int
    gap_analysis: str
    decision: str
    needs_revision: bool
    feedback: str


class LLMEducationalEvaluation(BaseModel):
    """Complete educational evaluation response from LLM (structured output)."""
    theme_relevance_score: int = Field(ge=1, le=5, description="Score 1-5 for Theme Relevance and Objectives")
    age_appropriateness_score: int = Field(ge=1, le=5, description="Score 1-5 for Age, Cognitive, and Scaffolding Appropriateness")
    narrative_engagement_score: int = Field(ge=1, le=5, description="Score 1-5 for Narrative and Emotional Engagement")
    educational_value_score: int = Field(ge=1, le=5, description="Score 1-5 for Educational Value and Concept Concretization")
    instruction_alignment_score: int = Field(ge=1, le=5, description="Score 1-5 for Instruction Alignment, QA, and Accessibility")
    score: float = Field(ge=1.0, le=5.0, description="Average of all five dimension scores (1.0-5.0)")
    gap_analysis: str = Field(description="'Sufficient' if research is adequate, 'Missing Info' if more research is needed")
    decision: str = Field(description="APPROVE, REVISE, or NEED_MORE_RESEARCH")
    needs_revision: bool = Field(description="True if draft needs revision")
    feedback: str = Field(description="Narrative summary paragraph of the evaluation")
    strengths: List[str] = Field(description="List of strengths found in the story")
    weaknesses: List[str] = Field(description="List of issues/weaknesses (ISSUE format when location-specific)")


class GevalSubCriteriaInput(BaseModel):
    """Structured input payload logged to Langfuse for each geval sub-criteria generation."""
    metric: str
    model: str
    system_prompt: str
    user_input: str
    criteria: str
    steps: list


class GevalSubCriteriaOutput(BaseModel):
    """Structured output payload logged to Langfuse for each geval sub-criteria generation."""
    score: int
    normalized: float
    reason: str


class RagasMetricInput(BaseModel):
    """Structured input payload logged to Langfuse for ragas_* metrics."""
    metric: str
    model: str
    system_prompt: str = ""
    user_input: str
    contexts_count: int
    contexts: list
    response: Optional[str] = None


class RagasMetricOutput(BaseModel):
    """Structured output payload logged to Langfuse for ragas_* metrics."""
    score: float


class FablesExtractInput(BaseModel):
    """Structured input payload logged to Langfuse for fables_extract_claims."""
    metric: str = "fables_extract_claims"
    model: str
    system_prompt: str = ""
    user_input: str
    story_length_chars: int


class FablesExtractOutput(BaseModel):
    """Structured output payload logged to Langfuse for fables_extract_claims."""
    claims_extracted: int
    claims: list


class FablesVerifyInput(BaseModel):
    """Structured input payload logged to Langfuse for fables_verify_all_claims."""

    metric: str = "fables_verify_all_claims"
    model: str
    system_prompt: str = ""
    user_input: str
    total_claims: int
    claims: list
    context_chars: int
    contexts: List[str] = Field(
        default_factory=list,
        description="Same list passed to RAGAS Context Relevance and FABLES (joined with --- at runtime).",
    )


class FablesVerifyOutput(BaseModel):
    """Structured output payload logged to Langfuse for fables_verify_all_claims."""

    faithful: int
    unfaithful: int
    partial_support: int = 0
    cant_verify: int
    verdicts: list
    summary: dict


class LLMCoherenceIssue(BaseModel):
    """Single coherence issue identified by LLM."""
    issue_type: str = Field(description="Type: character, item, plot, sentiment, structure")
    description: str = Field(description="Clear description of the issue")
    location: str = Field(
        description=(
            "Exact location in the story: paragraph number AND a short verbatim quote "
            "(max 15 words) from that paragraph. Format: 'Paragraf N: \"...kutipan...\"'"
            if LanguageConfig.SYSTEM_LANGUAGE == "en"
            else "Lokasi spesifik di cerita: nomor paragraf DAN kutipan singkat verbatim "
            "(maks 15 kata) dari paragraf tersebut. Format: 'Paragraf N: \"...kutipan...\"'"
        )
    )
    severity: str = Field(description="Severity: critical, major, or minor")
    suggestion: str = Field(
        description=(
            "Concrete rewrite suggestion targeting the identified location"
            if LanguageConfig.SYSTEM_LANGUAGE == "en"
            else "Saran penulisan ulang yang konkret, menargetkan lokasi yang teridentifikasi"
        )
    )


class LLMCoherenceEvaluation(BaseModel):
    """Complete coherence evaluation response from LLM."""
    coherence_score: float = Field(ge=0.0, le=10.0, description="Coherence score 0-10")
    issues: List[LLMCoherenceIssue] = Field(..., description="List of coherence issues found")
    summary: str = Field(
        ...,
        description=(
            "Brief summary of coherence quality"
            if LanguageConfig.SYSTEM_LANGUAGE == "en"
            else "Ringkasan singkat kualitas koherensi"
        ),
    )
    strengths: List[str] = Field(..., description="What the story does well for coherence")
    needs_revision: bool = Field(
        ...,
        description=(
            "True if narrative incoherence (Logicality or Consistency) "
            "is severe enough to warrant a revision"
        ),
    )
    revision_reason: str = Field(
        ...,
        description=(
            "Explanation of why a revision is or is not needed "
            "based on Logicality and Consistency"
        ),
    )


@dataclass
class CoherenceIssue:
    """A specific coherence issue with location and actionable suggestion."""
    issue_type: str   # "character", "item", "plot", "sentiment", "structure"
    description: str  # What's wrong
    location: str     # Where in the story (paragraph indicator or quote)
    severity: str     # "critical", "major", "minor"
    suggestion: str   # How to fix it

    def to_dict(self) -> dict:
        return asdict(self)
