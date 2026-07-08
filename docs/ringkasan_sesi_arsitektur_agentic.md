# Ringkasan Sesi: Arsitektur Agentic AI untuk Skripsi dan Publikasi Scopus

> **Tanggal**: 2026-06-09 s.d. 2026-06-13
> **Topik Utama**: Identifikasi paradigma arsitektur multi-agen, kondisi eksperimen ablation study (Baseline/Single/Multi), dan persiapan referensi arsitektur pembanding.

---

## 1. Sistem yang Dibangun

Sistem multi-agen pembuatan cerita anak edukatif berbasis LangGraph dengan komponen:

| Agen | Peran |
|:---|:---|
| `SupervisorAgent` | Orchestrator: Observe state -> Reason -> Route ke agen spesialis (Hierarchical ReAct) |
| `PlannerAgent` | Menyusun outline cerita, karakter, pesan moral |
| `ResearchAgent` | Riset via LightRAG (KG) dan Google Search Grounding |
| `WriterAgent` | Menulis cerita dari outline + konteks riset |
| `WriterDiagramAgent` | Membuat diagram Mermaid edukatif |
| `CriticAgent` | Mengevaluasi draf, keputusan: APPROVE / REVISE / NEED_MORE_RESEARCH |
| `DirectorAgent` | Menyusun skrip cerita untuk produksi |
| `ImageGeneratorAgent` | Menghasilkan ilustrasi cerita |

---

## 2. Paradigma Arsitektur yang Terimplementasi

### Keempat paradigma berikut TERPENUHI seluruhnya:

| Paradigma | Komponen | Bukti Kode |
|:---|:---|:---|
| **Plan-and-Solve** | PlannerAgent + ResearchAgent._plan_research() | Fase planning terpisah dari eksekusi di graph.py |
| **MRKL** | SupervisorAgent sebagai semantic router ke 7 agen | supervisor.py: SupervisorDecision.next_step (8 target) |
| **Self-Refine** | CriticAgent -> WriterAgent (loop iteratif) | graph.py: critique -> revision_prep -> writers -> merge -> critique |
| **BSM (Branch-Solve-Merge)** | Parallel dispatch writers + merge | graph.py: Send API -> writer_text + writer_diagram -> merge_writers |

### SupervisorAgent = Hierarchical ReAct (sudah ada, tidak perlu diubah):

```
Observe: _read_story_context(state) + _query_kg()
Reason:  SupervisorDecision.reasoning (LLM field)
Act:     supervisor_next -> route ke agen spesialis
Loop:    Berulang setiap ada input baru atau HITL feedback
```

### Reflexion direncanakan pada WriterAgent+CriticAgent (lintas sesi):
- PRD tersedia di: `docs/prd_reflexion_architecture.md`
- Komponen: ReflectionGenerator (post-finalize) + ReflectionRetriever (pre-write)
- Storage: SQLite di `Eval_Data/reflections.db`

---

## 3. Pola Multi-Agent (Referensi FareedKhan-dev)

Dari referensi https://github.com/FareedKhan-dev/all-agentic-architectures, sistem termasuk pola:

**Multi-Agent: Supervisor + Specialists** (paling tepat)

Perbedaan dengan referensi dasar:

| Aspek | Referensi | Sistem Ini |
|:---|:---|:---|
| Alur | Linear (parallel specialists -> writer -> END) | Directed state graph dengan loop revisi |
| Loop revisi | Tidak ada | Ada (CriticAgent, hingga MAX_REVISIONS) |
| Tool use | Web search saja | Web search + LightRAG KG (hybrid) |
| Memori | Tidak ada | LightRAG + Langfuse + Reflexion (SQLite) |
| HITL | Tidak ada | Ada (hitl_gate untuk persetujuan draf/rencana) |
| Paralelisme | 1 level | 2 level (BSM writers + BSM production) |

---

## 4. Kondisi Eksperimen Ablation Study (untuk Scopus)

### Tiga kondisi eksperimen (sudah diimplementasikan):

| Kondisi | Endpoint API | Arsitektur |
|:---|:---|:---|
| **Baseline** | `POST /baseline/generate` | Single LLM, tanpa RAG, tanpa agen |
| **Single Agent** | `POST /workflow/generate-single` | LightRAG + WriterAgent (satu pass, tanpa loop) |
| **Multi-Agent** | `POST /workflow/generate` | Full pipeline (Plan+Research+Write+Critique+Finalize) |

### Delta yang dapat diklaim di paper:
- **Baseline -> Single**: Kontribusi LightRAG RAG
- **Single -> Multi**: Kontribusi orkestrasi multi-agen (Plan-and-Solve + Self-Refine + BSM)

### Field baru di StoryState:
```python
workflow_mode: str  # "multi_agent" | "single_agent" | "baseline"
```

### Langfuse trace name per kondisi:
- `StoryGenerationWorkflow` (multi-agent)
- `SingleAgentWorkflow` (single agent)

---

## 5. Referensi Arsitektur Pembanding

Notebook asli dari FareedKhan-dev sudah diunduh ke:

```
src/workflows/
├── story_agent/                          <- Sistem utama
├── story_agent_supervisor_specialists/   <- Multi-Agent (Supervisor + Specialists)
│   └── multi_agent_supervisor_specialists.ipynb
├── story_agent_blackboard/               <- Blackboard (Shared Workspace)
│   └── multi_agent_blackboard.ipynb
├── story_agent_debate/                   <- Debate (N agents x K rounds)
│   └── multi_agent_debate.ipynb
├── story_agent_storm/                    <- STORM (Multi-perspective Research)
│   └── multi_agent_storm.ipynb
└── story_agent_meta_controller/          <- Meta-Controller (Router over Architectures)
    └── multi_agent_meta_controller.ipynb
```

Semua notebook belum dimodifikasi (konten asli dari repositori).

---

## 6. File Kunci yang Dimodifikasi di Sesi Ini

| File | Perubahan |
|:---|:---|
| `src/workflows/story_agent/graph.py` | Tambah `create_single_agent_workflow()` (single agent ablation) |
| `src/apps/api/routers/workflow.py` | Tambah endpoint `POST /generate-single` + SSE handler |
| `src/workflows/story_agent/state.py` | Tambah field `workflow_mode: str` |
| `docs/prd_reflexion_architecture.md` | PRD lengkap implementasi Reflexion (belum diimplementasikan) |

---

## 7. Rekomendasi untuk Sesi Berikutnya

1. **Adaptasi notebook referensi** ke domain cerita anak: Pilih 1-2 arsitektur dari `story_agent_blackboard/` atau `story_agent_storm/` untuk dikembangkan sebagai varian sistem.
2. **Implementasi Reflexion**: Ikuti PRD di `docs/prd_reflexion_architecture.md` untuk menambahkan pembelajaran lintas sesi pada WriterAgent.
3. **Jalankan ablation study**: Gunakan 3 endpoint (`/baseline/generate`, `/generate-single`, `/generate`) untuk menghasilkan 20 cerita per kondisi dan ukur delta FABLES + G-Eval + jumlah revisi.
4. **Penulisan Bab 5 (Future Work)**: Dokumentasikan Reflexion dan ekstensi ke arsitektur STORM/Blackboard sebagai arah pengembangan yang direkomendasikan.
