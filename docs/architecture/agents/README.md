# Dokumentasi per agen (Story Agent)

Penjelasan operasional tiap agen dalam pipeline LangGraph di [`src/workflows/story_agent/`](../../../src/workflows/story_agent/). Alur orkestrasi global tetap di [pengembangan_arsitektur_agentic_ai.md](../pengembangan_arsitektur_agentic_ai.md).

**Diagram lengkap (semua node, cabang, revisi, HITL, sub-agen kritik — tanpa tools):** [agent_graph_diagrams.md](../agent_graph_diagrams.md).

| Agen | Node graf (utama) | Dokumen |
|------|-------------------|---------|
| **Planner** | `planning` | [agent_planner.md](agent_planner.md) |
| **Research** | `research` | [agent_researcher.md](agent_researcher.md) |
| **Writer (teks)** | `writer_text` | [agent_writer.md](agent_writer.md) |
| **Critic** | `critique` | [agent_critic.md (Educational & Coherence Evaluator)](agent_critic.md) |
| **Critic Evaluator** | *(jalur finalize, bukan node revisi)* | [agent_critic_evaluator.md (GEval & Ragas Evaluator)](agent_critic_evaluator.md) |
| **Supervisor** | `supervisor_node` (interaktif) | [agent_supervisor.md](agent_supervisor.md) |
| **Image generator** | `writer_image` (produksi) | [agent_image_generator.md](agent_image_generator.md) |
| **Writer diagram** | `writer_diagram` | [agent_writer_diagram.md](agent_writer_diagram.md) |
| **Director** | `writer_director` | [agent_director.md](agent_director.md) |

**Bukan kelas agen:** node `merge_writers`, `revision_prep`, `production_gate`, `merge_production`, `finalize`, `ingest_sources` — dijelaskan di bagian routing pada dokumen arsitektur utama.

Setiap file `agent_*.md` memuat bagian **Diagram: tools & antarmuka eksekusi** (Mermaid): alur LLM terstruktur, Google Search / LightRAG (researcher), GenAI image (image generator), dll.
