"""
Agentic AI Architecture tab for the Streamlit evaluation dashboard.

Displays the full multi-agent pipeline structure including:
- LangGraph workflow overview
- Agent hierarchy and responsibilities
- Critic sub-evaluator pipeline
- Default prompts for each agent/evaluator
- Decision routing logic
"""

import streamlit as st
import pandas as pd


# ---------------------------------------------------------------------------
# Prompt constants (verbatim from prompts/en/ and eval_ragas.py)
# ---------------------------------------------------------------------------

_SUPERVISOR_PROMPT = """
You are the **Supervisor** — the primary orchestrator of the story-generation system.
You read the user's message and the current system state summary, then decide the next action.

## Responsibilities
You **do not perform tasks directly**. You analyze the request and delegate to the right specialist node.

## Routing Options (`next_step`)

| `next_step`    | Use when |
|----------------|----------|
| `planning`     | User requests a new story or no story exists yet. |
| `research`     | Key facts are missing before writing begins. |
| `writing`      | A story exists and the user wants to revise a specific part. |
| `critique`     | User requests quality evaluation on the existing story. |
| `finalize`     | User or HITL feedback approves the result. |
| `qa_response`  | Factual question answerable from available state content. |
| `director`     | User requests dialogue script / screenplay generation. |
| `FINISH`       | User explicitly ends the session. |

## Cost-Efficiency Principles
- **State-first**: Always check state content before routing to another agent.
- **Inline Q&A**: Answer questions from existing draft without calling an agent.
- **Avoid unnecessary loops**: Do not route to `critique` or `research` without a clear reason.
"""

_RESEARCHER_PROMPT = """
You are an expert Research Planner for an educational story writer.

Goal: Decompose a broad research request into 3–5 specific, targeted questions and select the best tool for each.

## Tools Available
1. **lightrag** (Knowledge Graph): historical facts, scientific concepts, established knowledge.
2. **web_search**: current events, latest news, very specific niche details.
3. **both**: comprehensive coverage (default when unsure).

## Instructions
1. Break down the Learning Objectives and Theme into 3–5 specific questions.
2. For each question, assign the best tool.
3. DEFAULT to `both` for comprehensive coverage.

OUTPUT: JSON representing `ResearchPlan` with list of `ResearchQuestion` objects.
"""

_WRITER_PROMPT = """
You are a Creative Writer specializing in educational stories.

Task: Write an engaging story that teaches while entertaining.

OUTPUT FORMAT:
- Start DIRECTLY with the story title.
- Then write the story content immediately.
- DO NOT include any introduction or closing commentary.
- JUST OUTPUT: Title + Story paragraphs. Nothing else.

FAITHFULNESS RULES (IMPORTANT):
- Every fact, number, scientific name, or factual claim MUST come from the Research Material provided.
- DO NOT invent facts not present in the research.
- Use imaginative narration (emotions, dialogue, atmosphere) without introducing new factual claims.

Inputs: target_age, theme, story_style, emotional_tone, story_length,
        story_outline, characters, moral_message, research_notes, critique_feedback.
"""

_CRITIC_PROMPT = """
You are an Expert Educational Evaluator Agent assessing story-based learning drafts across five key quality areas.

## Score Anchor Guide (Scale 1–5)
- **1 (Very Poor)**: Evidence of understanding or compliance is minimal, deviating far from the goal.
- **2 (Poor)**: Initial attempt but fundamental weaknesses hinder comprehension.
- **3 (Fair)**: Meets basic expectations, but feels rigid; requires substantial revision.
- **4 (Good)**: Concept conveyed well, meets pedagogical standards, minor room for improvement.
- **5 (Excellent)**: Outstanding execution, highly engaging, innovative, perfectly meets instructions.

## Five Evaluation Dimensions

1. **Theme Relevance & Objectives** (1–5)
   How strongly is the story grounded in the original request and theme?
   *(Constructive Alignment — Morris et al., 2021)*

2. **Age, Cognitive & Scaffolding Appropriateness** (1–5)
   Are vocabulary, sentence complexity, and plot appropriate for the target age?
   *(Cognitive load management — Yue et al., 2022)*

3. **Narrative & Emotional Engagement** (1–5)
   Does the story sustain reader attention and spark curiosity?
   *(Emotional & Behavioral Engagement — Zou et al., 2023)*

4. **Educational Value & Concept Concretization** (1–5)
   Are moral and academic messages naturally integrated and abstract concepts made concrete?
   *(Critical thinking & concretization — Yue et al., 2022)*

5. **Instruction Alignment, QA & Accessibility** (1–5)
   Does the draft comply with word count limits and specific user directives?
   *(QA in AWE systems — Fleckenstein et al., 2023)*

## Revision Decision Rules
- Score 1 or 2 on any dimension → **Return for Re-draft** (automatic)
- Score 3 on any dimension → Still requires significant revision
- All scores ≥ 4 → **Proceed to Polishing Stage**

## Output Fields
`theme_relevance_score`, `age_appropriateness_score`, `narrative_engagement_score`,
`educational_value_score`, `instruction_alignment_score`, `score` (avg), `gap_analysis`,
`decision` (APPROVE/REVISE/NEED_MORE_RESEARCH), `needs_revision`, `feedback`, `strengths`, `weaknesses`
"""

_COHERENCE_PROMPT = """
You are a literary expert and Semantic Coherence Analyst using an LLM-as-a-Judge system
to evaluate *Narrative Coherence* and *Faithfulness* based on the Event Horizon Model (EHM).

## EVALUATION CRITERIA

1. **Fabula & Logicality** (World Rules & Logic)
   Does the story establish a coherent causal network? Do character actions accord with context?

2. **Plot & Consistency** (Event Chain & Character Consistency)
   Is the chain of events self-contained and thematically consistent?
   No out-of-character behavior without a proper catalyst.

3. **Discourse** (Narrative Presentation)
   Readability, flow, and absence of rigidly repetitive sequences.

4. **Long-Term Causal Network** (Episodic Memory & Event Boundaries)
   Do later events causally follow earlier ones across time/place shifts?

5. **Knowledge Grounding & Faithfulness** (Structured Context & Hallucinations)
   Does the story utilize provided knowledge without hallucination or off-topic drift?

## Decision Logic
- **needs_revision = TRUE** if: fatal logical violations, ungrounded out-of-character behavior,
  or Objective Hallucinations contradicting structured knowledge.
- **needs_revision = FALSE** if: logically sound, factually grounded, well-presented.

Output: `coherence_score` (0–10), `issues[]` with severity, `needs_revision`, `revision_reason`, `summary`, `strengths`.
"""

_FABLES_EXTRACT_PROMPT = """
FABLES Claim Extraction (Kim et al., 2024; arXiv:2404.01261v2 — Appendix B)

Task: Extract ALL verifiable real-world statements from the educational story into atomic claims.

What to extract:
- Scientific facts, phenomena, processes; educational concepts; historical facts; properties of real entities
- Real-world claims even when spoken by fictional characters

Mandatory rules (per Appendix B / §2):
1. Each claim must be fully understood without additional story context — replace pronouns with entity names.
2. Place claims in temporal, locational, or causal context when possible.
3. Maximum 2 sentences per claim.
4. Separate claims with '- ' prefix on a new line.

DECONTEXTUALIZATION example:
  Story: "Budi learned that solar panels convert sunlight into electricity."
  Claim: "- Solar panels convert sunlight into electricity."

SKIP purely fictional events with no real-world factual content.
If no verifiable claims: reply exactly with: tidak ada
"""

_FABLES_VERIFY_PROMPT = """
FABLES Claim Verification (Kim et al., 2024; arXiv:2404.01261v2 — §2 Label Scheme)

Given: research context (including planner snippets) + one claim from an educational story.
Task: Choose ONE faithfulness label for the claim.

LABELS (use exact token on last line of your answer):
- FAITHFUL — claim accurately reflects facts supported by context.
- UNFAITHFUL — claim misrepresents or contradicts context.
- PARTIAL_SUPPORT — partially supported; goes beyond or slightly misrepresents context.
- CANT_VERIFY — insufficient evidence to support or refute; topic not covered.

Short examples:
  Context: "Creativity is a learnable skill."
  Claim: "Creativity is a genetic talent." → UNFAITHFUL
  Claim: "Aristotle defined creativity." → CANT_VERIFY

Output: 1–2 sentence reasoning, then last line = one of the four tokens exactly.
"""

_GEVAL_CRITERIA = {
    "Fluency": {
        "description": "How smoothly the text reads, focusing on grammar and syntax.",
        "steps": [
            "Identify grammatical errors or syntax issues.",
            "Evaluate natural sentence flow.",
            "Penalize awkward phrasing, fragments, or overly complex structures.",
            "Score 1–5 (5 = best fluency).",
        ],
    },
    "Consistency": {
        "description": "Whether the text maintains uniform style and tone throughout.",
        "steps": [
            "Check narrative voice and tone consistency throughout the story.",
            "Identify abrupt shifts in style, formality, or perspective.",
            "Verify uniform level of educational richness from start to finish.",
            "Score 1–5 (5 = most consistent).",
        ],
    },
    "Clarity": {
        "description": "How easily the text can be understood by the target reader.",
        "steps": [
            "Evaluate clarity and directness of language.",
            "Check if complex ideas are accessible and jargon-free or explained.",
            "Identify vague, ambiguous, or confusing parts.",
            "Score 1–5 (5 = clearest).",
        ],
    },
    "Conciseness": {
        "description": "Whether the text is free of unnecessary words or details.",
        "steps": [
            "Identify filler words, padding, or over-explanation.",
            "Check that each paragraph contributes meaningfully.",
            "Penalize verbose or padded writing.",
            "Score 1–5 (5 = most concise).",
        ],
    },
    "Repetitiveness": {
        "description": "Absence of redundant sentences, phrases, or ideas (5 = no repetition).",
        "steps": [
            "Scan for repeated sentences, phrases, or ideas without added value.",
            "Identify redundant descriptions of characters, settings, or events.",
            "Check for unnecessarily restated educational concepts.",
            "Score 1–5 (5 = no repetition, 1 = highly repetitive).",
        ],
    },
}


# ---------------------------------------------------------------------------
# Mermaid diagrams
# ---------------------------------------------------------------------------

_PIPELINE_DIAGRAM = """
flowchart TD
    classDef agent  fill:#1e3a5f,color:#ffffff,stroke:#3b82f6,stroke-width:2px
    classDef gate   fill:#3f2d00,color:#ffffff,stroke:#eab308,stroke-width:2px
    classDef prod   fill:#14421b,color:#ffffff,stroke:#22c55e,stroke-width:2px
    classDef decide fill:#3b0764,color:#ffffff,stroke:#a855f7,stroke-width:2px
    classDef super  fill:#7f1d1d,color:#ffffff,stroke:#ef4444,stroke-width:2px

    sup["Supervisor Agent"]:::super
    planning["Planner Agent"]:::agent
    research["Research Agent"]:::agent
    dispatch["dispatch_to_writers"]:::gate
    wtext["Writer Agent (text)"]:::agent
    merge["merge_writers"]:::gate
    critique["Critic Agent"]:::agent
    decide["should_continue_or_finalize"]:::decide
    revprep["revision_prep"]:::gate
    prod["production_gate"]:::prod

    sup -->|"planning"| planning
    sup -->|"research"| research
    sup -->|"writing"| wtext
    planning --> research
    research --> dispatch
    dispatch --> wtext
    wtext --> merge
    merge --> critique
    critique --> decide
    decide -->|"REVISE"| revprep
    decide -->|"NEED_MORE_RESEARCH"| research
    decide -->|"APPROVE / max revisions"| prod
    revprep --> dispatch
"""

_CRITIC_DIAGRAM = """
flowchart TD
    classDef eval  fill:#1e3a5f,color:#ffffff,stroke:#3b82f6,stroke-width:2px
    classDef opt   fill:#fef9c3,color:#3f2d00,stroke:#eab308,stroke-width:1px,stroke-dasharray:5 5
    classDef out   fill:#14421b,color:#ffffff,stroke:#22c55e,stroke-width:2px
    classDef decide fill:#7f1d1d,color:#ffffff,stroke:#ef4444,stroke-width:2px

    start["critique(state)"]:::eval

    subgraph parallel["Every Iteration — asyncio.gather"]
        edu["Educational Evaluator (5 dims, 1-5)"]:::eval
        coh["Coherence Evaluator (5 criteria, 0-10)"]:::eval
    end

    merge["StructuredCritique — aggregate decision"]:::out

    subgraph optional["Finalize Only"]
        ragas["RAGAS (AnswerRelevancy + ContextRelevance)"]:::opt
        geval["G-Eval (5 sub-criteria, Fluency/Consistency/…)"]:::opt
        fables["FABLES Faithfulness (claim verification)"]:::opt
    end

    decide["APPROVE / REVISE / NEED_MORE_RESEARCH"]:::decide

    start --> parallel
    edu --> merge
    coh --> merge
    merge -.-> optional
    merge --> decide
"""


# ---------------------------------------------------------------------------
# Routing decision table
# ---------------------------------------------------------------------------

_DECISION_ROWS = [
    {
        "Condition": "`educational_passed` AND `alignment_passed` AND no critical/major coherence issues",
        "Decision": "APPROVE",
        "Next Stage": "`finalize` → production",
    },
    {
        "Condition": "`revision_count` ≥ `MAX_REVISIONS` (= 3) after increment",
        "Decision": "APPROVE (max revisions)",
        "Next Stage": "Force to production",
    },
    {
        "Condition": "`NEED_MORE_RESEARCH` flag OR `'Missing' in gap_analysis` AND alignment passed",
        "Decision": "NEED_MORE_RESEARCH",
        "Next Stage": "Back to `research`",
    },
    {
        "Condition": "`needs_revision` (coherence) OR critical/major issue OR alignment failed",
        "Decision": "REVISE",
        "Next Stage": "Back to `dispatch_to_writers`",
    },
]

_AGENT_ROWS = [
    {
        "Agent": "SupervisorAgent",
        "Node": "supervisor",
        "Role": "Routes user messages to the correct workflow stage; does NOT execute tasks directly",
        "Scale": "N/A",
        "Affects Routing": "Yes (entry point)",
    },
    {
        "Agent": "PlannerAgent",
        "Node": "planning",
        "Role": "Parses user request; creates story outline, characters, moral message, writer selection",
        "Scale": "N/A",
        "Affects Routing": "No",
    },
    {
        "Agent": "ResearchAgent",
        "Node": "research",
        "Role": "Plans questions; queries Web (Google) and/or LightRAG Knowledge Graph per question",
        "Scale": "N/A",
        "Affects Routing": "No",
    },
    {
        "Agent": "WriterAgent",
        "Node": "writer_text",
        "Role": "Generates first draft or targeted paragraph-level revision via StoryCanvas",
        "Scale": "N/A",
        "Affects Routing": "No",
    },
    {
        "Agent": "CriticAgent",
        "Node": "critique",
        "Role": "Orchestrates parallel evaluation; aggregates into StructuredCritique + routing decision",
        "Scale": "N/A",
        "Affects Routing": "Yes (APPROVE / REVISE / NEED_MORE_RESEARCH)",
    },
    {
        "Agent": "EducationalEvaluator",
        "Node": "(sub-critic)",
        "Role": "5-dimension educational rubric via structured LLM output",
        "Scale": "1.0–5.0",
        "Affects Routing": "Yes (threshold 4.0)",
    },
    {
        "Agent": "CoherenceEvaluator",
        "Node": "(sub-critic)",
        "Role": "5-criteria narrative coherence (EHM model); issues tagged critical/major/minor",
        "Scale": "0.0–10.0",
        "Affects Routing": "Yes (critical/major issues trigger REVISE)",
    },
    {
        "Agent": "GEvalEvaluator",
        "Node": "(finalize only)",
        "Role": "5 parallel sub-criteria via DeepEval G-Eval (Liu et al., 2023); averaged raw + normalized",
        "Scale": "1–5 raw / 0–1 norm",
        "Affects Routing": "No — logging only",
    },
    {
        "Agent": "RagasEvaluator",
        "Node": "(finalize only)",
        "Role": "Answer Relevancy + Context Relevance via RAGAS framework; 3 retries, 90s timeout",
        "Scale": "0.0–1.0",
        "Affects Routing": "No — logging only",
    },
    {
        "Agent": "FABLES",
        "Node": "(finalize only)",
        "Role": "Claim-level faithfulness: extract ≤10 claims, verify each vs. contexts (Kim et al., 2024)",
        "Scale": "0.0–1.0",
        "Affects Routing": "No — logging only",
    },
]


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_mermaid(code: str) -> None:
    """Render Mermaid diagram using a simple HTML component."""
    import streamlit.components.v1 as components
    html = f"""
    <div class="mermaid">
    {code.strip()}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true }});
    </script>
    """
    components.html(html, height=450, scrolling=True)


def render_architecture_tab() -> None:
    st.header("Arsitektur Agentic AI")
    st.markdown(
        "Pipeline multi-agen berbasis **LangGraph** (`StateGraph`) yang mengorkestrasikan "
        "pembuatan cerita edukatif secara end-to-end. State global bertipe **`StoryState`** "
        "memungkinkan transfer konteks terstruktur antar agen yang berjalan secara berurutan maupun paralel."
    )

    # --- Section: Comparison Summary ---
    from lib.baseline_loader import (
        load_baseline_df,
        load_current_df,
        latest_baseline_csv_path,
        latest_current_csv_path,
        load_traces_csv,
    )
    from lib.analysis_utils import add_language_col

    st.subheader("Ringkasan Perbandingan Performa")
    st.markdown(
        "Tabel berikut merangkum rata-rata metrik utama untuk sistem **Agentic AI** vs **Baseline**. "
        "Nilai yang dicetak tebal menunjukkan performa terbaik di setiap kolom."
    )

    baseline_raw = load_baseline_df()
    current_raw = load_current_df()

    if baseline_raw is not None and current_raw is not None:
        baseline = add_language_col(baseline_raw)
        current = add_language_col(current_raw)

        def get_group_df(group_name, metric_col, *, agg: str = "mean"):
            rows = []
            for df, name in [(current, "Agentic AI (Gemini 2.5 Flash)"), (baseline, "Baseline (Gemini 2.5 Flash)")]:
                sub_id = df[df["language"] == "id"][metric_col]
                sub_en = df[df["language"] == "en"][metric_col]
                sub_all = df[metric_col]

                if agg == "sum":
                    id_val = pd.to_numeric(sub_id, errors="coerce").sum()
                    en_val = pd.to_numeric(sub_en, errors="coerce").sum()
                    tot_val = pd.to_numeric(sub_all, errors="coerce").sum()
                else:
                    id_val = pd.to_numeric(sub_id, errors="coerce").mean()
                    en_val = pd.to_numeric(sub_en, errors="coerce").mean()
                    tot_val = pd.to_numeric(sub_all, errors="coerce").mean()
                rows.append({
                    "Arsitektur": name,
                    f"{group_name} (ID)": round(float(id_val), 4) if pd.notna(id_val) else 0.0,
                    f"{group_name} (EN)": round(float(en_val), 4) if pd.notna(en_val) else 0.0,
                    f"{group_name} (Total)": round(float(tot_val), 4) if pd.notna(tot_val) else 0.0,
                })
            return pd.DataFrame(rows)

        def highlight_max(s):
            if s.name == "Arsitektur":
                return [''] * len(s)
            is_max = s == s.max()
            return ['font-weight: bold; background-color: rgba(59, 130, 246, 0.1)' if v else '' for v in is_max]

        # Table 1: RAGAS
        df_ragas = get_group_df("RAGAS", "ragas_standard_faithfulness")
        st.dataframe(
            df_ragas.style.apply(highlight_max).format({c: "{:.3f}" for c in df_ragas.columns if c != "Arsitektur"}),
            use_container_width=True, hide_index=True
        )

        # Table 2: FABLES
        df_fables = get_group_df("FABLES", "fables_faithfulness")
        st.dataframe(
            df_fables.style.apply(highlight_max).format({c: "{:.3f}" for c in df_fables.columns if c != "Arsitektur"}),
            use_container_width=True, hide_index=True
        )

        # Table 3: G-Eval
        df_geval = get_group_df("GEVAL", "geval_coherence_normalized")
        st.dataframe(
            df_geval.style.apply(highlight_max).format({c: "{:.3f}" for c in df_geval.columns if c != "Arsitektur"}),
            use_container_width=True, hide_index=True
        )

    else:
        base_p = latest_baseline_csv_path()
        cur_p = latest_current_csv_path()

        if base_p is None:
            st.warning(
                "Data baseline tidak ditemukan. Pastikan CSV export tersedia di `Eval_Data/Baselines/Traces/`."
            )
        if cur_p is None:
            st.warning(
                "Data current tidak ditemukan. Pastikan CSV export tersedia di `Eval_Data/Traces/`."
            )

        if cur_p is not None:
            try:
                df_raw = load_traces_csv(cur_p)
                if "name" in df_raw.columns:
                    names = (
                        df_raw["name"].astype(str).str.strip('"').str.strip("'").value_counts().to_dict()
                    )
                    if names and set(names.keys()) == {"BaselineWikiEvalWorkflow"}:
                        st.warning(
                            "CSV current (`Eval_Data/Traces/`) berisi hanya workflow baseline "
                            "(`BaselineWikiEvalWorkflow`). Export trace Agentic AI diperlukan "
                            "untuk membandingkan."
                        )
            except Exception:
                pass

        st.warning("Data baseline atau current tidak lengkap untuk merender tabel perbandingan.")

    # --- Section 1: Pipeline overview ---
    st.subheader("1. Alur Keseluruhan Pipeline")
    render_mermaid(_PIPELINE_DIAGRAM)
    st.caption(
        "Supervisor mengorkestrasikan routing awal. Setelah masuk ke pipeline generasi, "
        "alur berjalan: Planning → Research → Writer(s) → Critique → keputusan routing. "
        "Self-reflection loop berulang hingga APPROVE atau MAX_REVISIONS = 3."
    )

    # --- Section 2: Agent hierarchy table ---
    st.subheader("2. Hierarki Agen & Sub-Evaluator")

    df_agents = pd.DataFrame(_AGENT_ROWS)
    st.dataframe(
        df_agents,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Agent": st.column_config.TextColumn("Agent", width="medium"),
            "Node": st.column_config.TextColumn("Node", width="small"),
            "Role": st.column_config.TextColumn("Peran", width="large"),
            "Scale": st.column_config.TextColumn("Skala", width="small"),
            "Affects Routing": st.column_config.TextColumn("Routing", width="small"),
        },
    )

    # --- Section 3: Critic evaluation pipeline ---
    st.subheader("3. Pipeline Evaluasi Critic Agent")
    render_mermaid(_CRITIC_DIAGRAM)

    col1, col2 = st.columns(2)
    with col1:
        st.info(
            "**Setiap Iterasi** (mempengaruhi routing):\\n"
            "- Educational Evaluator (5 dimensi, skala 1–5, threshold 4.0)\\n"
            "- Coherence Evaluator (5 kriteria EHM, skala 0–10)"
        )
    with col2:
        st.warning(
            "**Hanya saat Finalize** (logging only):\\n"
            "- G-Eval (5 sub-kriteria paralel, 1–5 / 0–1 normalized)\\n"
            "- RAGAS Answer Relevancy + Context Relevance (0–1)\\n"
            "- FABLES Faithfulness — claim-level (0–1)"
        )

    # --- Section 4: Decision routing table ---
    st.subheader("4. Logika Keputusan Routing (Critic)")
    df_dec = pd.DataFrame(_DECISION_ROWS)
    st.dataframe(df_dec, use_container_width=True, hide_index=True)

    # --- Section 5: Evaluator specifications ---
    st.subheader("5. Spesifikasi Evaluator")

    eval_data = [
        {
            "Evaluator": "Educational (5 dims)",
            "Framework": "LLM-as-a-Judge (structured output)",
            "Scale": "1–5 per dim; avg → overall",
            "Threshold": "≥ 4.0 to pass",
            "Timing": "Every iteration",
            "Reference": "Morris et al. 2021; Yue et al. 2022; Zou et al. 2023",
        },
        {
            "Evaluator": "Coherence (EHM)",
            "Framework": "LLM-as-a-Judge (structured output)",
            "Scale": "0.0–10.0",
            "Threshold": "critical/major issues → REVISE",
            "Timing": "Every iteration",
            "Reference": "Event Horizon Model (EHM)",
        },
        {
            "Evaluator": "G-Eval (5 sub-criteria)",
            "Framework": "DeepEval G-Eval",
            "Scale": "1–5 raw; 0–1 normalized",
            "Threshold": "N/A (logging)",
            "Timing": "Finalize only",
            "Reference": "Liu et al. 2023; arXiv:2303.16634",
        },
        {
            "Evaluator": "RAGAS (AR + CR)",
            "Framework": "RAGAS",
            "Scale": "0.0–1.0",
            "Threshold": "N/A (logging)",
            "Timing": "Finalize only",
            "Reference": "RAGAS framework",
        },
        {
            "Evaluator": "FABLES Faithfulness",
            "Framework": "Claim-level LLM verification",
            "Scale": "0.0–1.0 (faithful / verifiable)",
            "Threshold": "N/A (logging)",
            "Timing": "Finalize only",
            "Reference": "Kim et al. 2024; arXiv:2404.01261v2",
        },
    ]
    st.dataframe(pd.DataFrame(eval_data), use_container_width=True, hide_index=True)

    # --- Section 6: Default prompts ---
    st.subheader("6. Default Prompts")

    with st.expander("Supervisor Prompt"):
        st.code(_SUPERVISOR_PROMPT, language="markdown")

    with st.expander("Research Planner Prompt"):
        st.code(_RESEARCHER_PROMPT, language="markdown")

    with st.expander("Writer Agent Prompt"):
        st.code(_WRITER_PROMPT, language="markdown")

    with st.expander("Critic — Educational Evaluator Prompt"):
        st.code(_CRITIC_PROMPT, language="markdown")

    with st.expander("Critic — Coherence Evaluator Prompt"):
        st.code(_COHERENCE_PROMPT, language="markdown")

    with st.expander("FABLES — Claim Extraction Prompt"):
        st.code(_FABLES_EXTRACT_PROMPT, language="markdown")

    with st.expander("FABLES — Claim Verification Prompt"):
        st.code(_FABLES_VERIFY_PROMPT, language="markdown")

    with st.expander("G-Eval — 5 Sub-Criteria Definitions"):
        for name, info in _GEVAL_CRITERIA.items():
            st.markdown(f"**{name}** — {info['description']}")
            for step in info["steps"]:
                st.markdown(f"  - {step}")
        st.markdown("---")
        st.caption("Framework: DeepEval G-Eval (Liu et al., 2023; arXiv:2303.16634). "
                   "Raw scale 1–5; normalized 0–1. Executed in parallel per sub-criterion.")
