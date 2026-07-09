# Skripsi Documentation

Welcome to the documentation for the Skripsi project: *Analisis Kinerja Agentic AI dan LightRAG*. This documentation is organized into key sections to help you navigate the system architecture, development guides, API references, and research materials.

## 📚 Key Sections

### 🏗️ Architecture

Understanding how the system is built.

- [System Overview](architecture/system_overview.md): High-level architecture of the Agentic AI and LightRAG integration.
- [Agentic AI workflow (planning → critic)](architecture/pengembangan_arsitektur_agentic_ai.md): Orchestration overview—`StoryState`, prompts, revision routing, API mapping (LangGraph story pipeline).
- **Per-agent docs:** [agents/README.md](architecture/agents/README.md) — planner, researcher, writer, critic, supervisor, image, diagram, director (one Markdown file each).
- **Full LangGraph diagrams (all nodes, loops, HITL, critic sub-agents, no tools):** [agent_graph_diagrams.md](architecture/agent_graph_diagrams.md).
- [LightRAG Integration](architecture/lightrag_integration.md): Details on how LightRAG is implemented and configured.
- **LightRAG (folder):** [Index](architecture/lightrag/README.md) — [EN spec](architecture/lightrag/lightrag_specification_en.md), [ID spec](architecture/lightrag/lightrag_specification_id.md), [WikiEval development log](architecture/lightrag/Dokumentasi_Pengembangan_LightRAG.md).
- [Stream Output Flow](architecture/stream_output_flow.md): Explanation of the SSE streaming mechanism for story generation.

### 📊 Datasets & estimates

- [Dataset word count & cost estimation](datasets/dataset_cost_estimation.md): NarrativeQA / WP-STORIES / tell_me_a_story statistics and Gemini 2.5 Flash Lite ingestion cost estimate.

### 📖 Guides

 Practical instructions for developers and authors.

- [Quickstart](guides/quickstart.md): Get up and running with the project quickly.
- [Configuration Guide](configuration.md): Complete list of environment variables (`.env`), LLM providers, and agent parameters.
- [Authoring Workflow](guides/authoring_workflow.md): How to create story-based learning content.
- [Story-Based Learning Playbook (from agent implementation)](story_based_learning_playbook.md): Narrative, thesis-friendly mapping from code-level rubric + decision loops → story-based learning workflow.
- [Narrative Styles](guides/narrative_styles.md): Reference for available story and narrative styles.
- [Replay FABLES / RAGAS on Langfuse traces](replay_faithfulness_langfuse.md): flags, backup, import.
- [Restore traces after a bad replay](traces_restore_after_bad_replay.md): backup + `--traces-csv` workflow.
- [Sampling trace terbaru (min, median, max) vs `Images_Faithfulness_10`](faithfulness_sampling_latest_vs_images_faithfulness_10.md): ringkasan sampling `fables_faithfulness` dan perbandingan verdict klaim dengan HTML visualisasi.

### 🔌 API Reference

Technical documentation for the backend API.

- [Assessment API](api/assessment_api.md): Endpoints for the assessment system.
- [Story Generation API](api/story_generation.md): Endpoints for generating stories.

### 🧠 Concepts

Theoretical background and design principles.

- [Agentic AI Principles](concepts/agentic_ai_principles.md): Core principles driving the agentic design.
- [Story Agent Reference](architecture/agent_reference.md): Detailed documentation of all agents in the systems.

### 🔬 Research

Academic background and research notes.

- [Original Proposal](research/original_proposal.md): The initial research proposal.
- [Research Notes](research/research_notes.md): Ongoing research findings and notes.

## 🗃️ Archive

Old documentation and fix logs are kept in the [Archive](archive/) for historical reference.

## 📊 Project Status

Check the current status and roadmap in [Project Status](PROJECT_STATUS.md).
