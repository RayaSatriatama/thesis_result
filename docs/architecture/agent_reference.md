# Story Agent Reference

This document gives an **English overview** of the agents in the story workflow. **Authoritative per-agent notes** (parameters, prompts, rubrics) are in **[agents/README.md](agents/README.md)** — one Markdown file per agent (e.g. [agent_planner.md](agents/agent_planner.md), [agent_critic.md](agents/agent_critic.md)).

Each agent below is a specialized component with specific roles, tools, and prompts.

## 1. Planner Agent (`PlannerAgent`)

**Role**: The architect of the story. It analyzes the user's request, plans the narrative structure, and decides which specialist writers to employ.

- **Source**: `src/workflows/story_agent/agents/planner.py`
- **Model**: Gemini 2.5 Flash (via Vertex AI)

### Capabilities

- **Request Analysis**: Parses natural language requests into structured parameters (theme, age, style).
- **Narrative Planning**: Creates a 4-part story outline (Introduction, Conflict, Climax, Resolution).
- **Character Design**: Generates character profiles suitable for the target audience.
- **Writer Selection**: Dynamically activates `text`, `image`, or `diagram` writers based on content needs.

### Input/Output

- **Input**: User message, Research notes (optional).
- **Output**: `PlannerOutput` (JSON) containing story plan and `active_writers` list.

### Prompts

- **`PLANNER_UNIFIED_PROMPT`**: The core driver. It combines request parsing, story planning, and writer selection into a single chain-of-thought prompt.

### Tools

- **Structured Output (Native)**: Executed via `llm.with_structured_output(PlannerOutput)` to enforce strict JSON schema.
- **Langfuse (Integration)**: Traces execution via `self.langfuse.start_span()`.

---

## 1. Supervisor Agent (`SupervisorAgent`)

**Role**: The workflow orchestrator. It routes the story generation process to the appropriate team capabilities based on the current state.

- **Source**: `src/workflows/story_agent/agents/supervisor.py`
- **Model**: Gemini 2.5 Flash

### Capabilities

- **State Analysis**: Evaluates current progress (research, outline, draft, revisions).
- **Routing**: Decides the next step in the workflow (Research, Planning, Writing, Critique, Finalize).
- **Flow Control**: Manages the transitions between agents.

### Input/Output

- **Input**: Current `StoryState` (context, drafted content, scores).
- **Output**: `SupervisorDecision` (next_step, reasoning).

### Prompts

- **`SUPERVISOR_PROMPT`**: Instructions for routing logic based on state completeness.

### Tools

- **Structured Router (Native)**: Executed via `llm.with_structured_output(SupervisorDecision)` to determine control flow.

---

## 2. Researcher Agent (`ResearcherAgent`)

**Role**: The knowledge gatherer. It ensures the story is factually accurate and educationally robust using a "Plan-Execute-Verify" loop.

- **Source**: `src/workflows/story_agent/agents/researcher.py`
- **Model**: Gemini 2.5 Flash (faster inference)

### Capabilities

- **Research Planning**: Decomposes topics into specific research questions.
- **Tool Selection**: Decides whether to use Web Search (current events) or Knowledge Graph (established facts).
- **Gap Analysis**: Verifies if gathered info meets learning objectives; loops back if gaps exist.
- **Synthesis**: Compiles findings into structured markdown notes.

### Input/Output

- **Input**: Theme, Target Age, Learning Objectives.
- **Output**: Research notes (markdown) and source citations.

### Prompts

- **`RESEARCH_PLANNER_PROMPT`**: Breaks down topics into questions.
- **`RESEARCHER_WEB_PROMPT`**:Optimizes queries for Google Search.
- **`RESEARCH_GAP_ANALYSIS_PROMPT`**: Evaluates completeness of findings.

### Tools

- **Google Search (Native)**: Executed via `_search_web()` using `GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())])`.
- **LightRAG (Custom)**: Executed via `_query_kg()` calling `self.lightrag.query(mode="hybrid")`.
- **Langfuse (Integration)**: Traces execution via `self.langfuse.start_span()`.

---

## 3. Writer Agent (`WriterAgent`)

**Role**: The storyteller. It drafts the narrative content and handles revisions.

- **Source**: `src/workflows/story_agent/agents/writer.py`
- **Model**: Gemini 2.5 Flash

### Capabilities

- **Drafting**: meaningful, age-appropriate narrative generation.
- **Style Adaptation**: Supports specific styles (e.g., "Narrative", "Fable", "Sci-Fi").
- **Canvas Management**: Maintains the `StoryCanvas` state.
- **Targeted Revision**: Performs surgical edits using a Search/Replace mechanism based on critique.

### Input/Output

- **Input**: Story Plan, Research Notes, Previous Draft (if revising).
- **Output**: Story Content (Markdown) and updated `StoryCanvas`.

### Prompts

- **`WRITER_PROMPT`**: Base narrative instructions.
- **`WRITER_INSTRUCTIONS_PROMPT`**: Enhancements for specific narrative styles (e.g., "Show, Don't Tell").

### Tools

- **StoryCanvas (State)**: Managed via `StoryCanvas.initialize_from_text()` to track narrative structure.
- **File Editor (Custom)**: Executed via `replace_in_files()` (from `vendor_file_edit.py`) for regex-based text replacement.
- **Langfuse (Integration)**: Traces drafting and revision via `self.langfuse.start_span()`.

---

## 4. Writer Diagram Agent (`WriterDiagramAgent`)

**Role**: The visual explainer. It creates educational diagrams to simplify complex concepts.

- **Source**: `src/workflows/story_agent/agents/writer_diagram.py`
- **Model**: Gemini 2.5 Flash

### Capabilities

- **Visual Planning**: Decides the best diagram type (Flowchart, Mindmap, Cycle).
- **Mermaid Generation**: Writes valid Mermaid.js code.
- **Rendering**: Converts Mermaid code to PNG images.

### Input/Output

- **Input**: Story Outline, Research Notes.
- **Output**: Mermaid Code and PNG file path.

### Prompts

- **`DIAGRAM_SYSTEM_PROMPT`**: Guidelines for valid Mermaid syntax and educational clarity.
- **`DIAGRAM_USER_PROMPT`**: Context-specific request.

### Tools

- **Mermaid Renderer (Custom)**: Executed via `render_mermaid()` (from `vendor_mermaid.py`) using `mmdc` CLI.
- **Langfuse (Integration)**: Traces diagram generation via `self.langfuse.start_span()`.

---

## 5. Image Generator Agent (`ImageGeneratorAgent`)

**Role**: The illustrator. It creates visual scenes to enhance engagement.

- **Source**: `src/workflows/story_agent/agents/image_generator.py`
- **Model**: Gemini 2.5 Flash Image (Imagen 3 backend)

### Capabilities

- **Scene Extraction**: Identifies key moments in the story to illustrate.
- **Prompt Engineering**: Optimizes prompts with art styles and mood (e.g., "watercolor", "digital art").
- **Generation**: Produces high-quality images.

### Input/Output

- **Input**: Story Draft, Character Descriptions.
- **Output**: List of generated image paths.

### Prompts

- **`IMAGE_GEN_SCENES_PROMPT`**: Extracts illustratable scenes.
- **`IMAGE_GEN_STYLE_PROMPT`**: Formats the generation prompt with style parameters.

### Tools

- **Imagen 3 (Native)**: Executed via `client.models.generate_content()` on `gemini-2.5-flash-image`.

---

## 6. Critic Agent (`CriticAgent`)

**Role**: The quality assurance expert. Evaluate the story for educational value and narrative coherence.

- **Source**: `src/workflows/story_agent/agents/critic/agent.py` (paket `critic/`)
- **Model**: Dikonfigurasi via `get_llm_for_agent("critic", …)` (lihat `settings` / provider).

### Capabilities

- **Dual Evaluation**: **EducationalEvaluator** (rubrik lima dimensi) dan **CoherenceEvaluator** (koherensi naratif LLM-as-a-Judge).
- **Structured Feedback**: Menghasilkan `StructuredCritique`, umpan balik untuk Writer, dan `revision_targets`.
- **Decision Making**: Keputusan agregat termasuk `APPROVE`, `REVISE`, `NEED_MORE_RESEARCH` (selaras dengan `graph.py`).

### Input/Output

- **Input**: Story Draft, Target Age, Learning Objectives, konteks rencana, dll. (`StoryState`).
- **Output**: Skor edukasi (1–5), `coherence_score` (0–10), `critique_feedback`, `structured_critique`, increment `revision_count`.

### Prompts

- **`critic`** (registry): Rubrik edukasi.
- **`critic_coherence`**: Evaluasi koherensi (Fabula/Plot/Discourse, grounding).

### Integrations

- **Langfuse (opsional)**: Span/generation/score untuk jejak evaluasi.
- Evaluator tambahan (RAGAS, G-EVAL) dapat dipanggil di jalur finalize sesuai konfigurasi; lihat `agent.py`.
