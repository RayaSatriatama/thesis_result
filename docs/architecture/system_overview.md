# Arsitektur Sistem

## Overview

Sistem ini mengimplementasikan arsitektur hibrida **Agentic AI** (orkestrasi LangGraph) dan **LightRAG** (retrieval berbasis knowledge graph) untuk pembuatan cerita pembelajaran yang koheren dan dapat ditelusuri ke sumber pengetahuan.

## Komponen Utama

### 1. Agentic AI (Orchestrator)

```
┌─────────────────────────────────────┐
│       Narrative Agent               │
│  ┌──────────┐  ┌──────────┐        │
│  │ Planner  │  │ Executor │        │
│  └────┬─────┘  └────┬─────┘        │
│       │             │               │
│       ▼             ▼               │
│  ┌──────────────────────────┐      │
│  │    Tool / Integrations   │      │
│  │  - Writers (Text/Img/Diag)   │  │
│  │  - LightRAG client       │      │
│  │  - Web search (opsional) │      │
│  └──────────────────────────┘      │
└─────────────────────────────────────┘
```

**Responsibilities:**

- Planning: Decompose story generation task
- Tool Use: Call LightRAG untuk knowledge retrieval
- Self-Reflection: Evaluate output quality

### 2. LightRAG Integration

```
┌─────────────────────────────────┐
│         LightRAG Tool           │
│  ┌──────────────────────────┐  │
│  │   Knowledge Graph        │  │
│  │  - Entities              │  │
│  │  - Relations             │  │
│  │  - Embeddings            │  │
│  └──────────────────────────┘  │
│                                 │
│  Query Modes:                   │
│  - Local: Entity-focused        │
│  - Global: Community summaries  │
│  - Hybrid: Combined             │
│  - Mix: KG + Vector             │
└─────────────────────────────────┘
```

**Dual-Level Retrieval:**

- Entity level: Character, objects, concepts
- Relation level: Connections, dependencies

### 3. Evaluation (Critic Agent & observabilitas)

**Critic Agent** (`src/workflows/story_agent/agents/critic/`) menggabungkan evaluasi **edukasi** (rubrik lima dimensi, skala 1–5) dan **koherensi naratif** (skor 0–10 + daftar isu). Hasil diserialkan ke `structured_critique` dan dapat dicatat di Langfuse (span/generation/score).

#### RAGAS Metrics (opsional / eksperimen)

| Metric | Formula | Deskripsi |
|--------|---------|-----------|
| Faithfulness | Supported / Total Claims | KG alignment |
| Context Recall | Retrieved Relevant / Total | Retrieval quality |

## Data Flow

### Story Generation Pipeline

```
1. Input Prompt
   ↓
2. Agent Planning
   ├─ Parse requirements
   └─ Create subtasks
   ↓
3. Knowledge Retrieval (LightRAG / web, sesuai rencana riset)
   ├─ Query KG
   └─ Hybrid search
   ↓
4. Writing (parallel writers sesuai `active_writers`)
   ↓
5. Critique (educational + coherence)
   ├─ Revisi / riset ulang / lanjut
   └─ Loop sampai batas atau persetujuan
   ↓
6. Output Story (dan fase produksi opsional)
```

### Evaluation Pipeline (ringkas)

```
1. Generated Stories
   ↓
2. Critic (LLM-as-a-Judge): educational + coherence
   ↓
3. RAGAS / metrik tambahan (opsional, jika dikonfigurasi)
   ↓
4. Statistical Analysis & laporan (eksperimen)
```

## Implementation Details

### State Machine untuk Narrative Agent

```python
class NarrativeAgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    REFLECTING = "reflecting"
    DONE = "done"
```

### Memory Architecture

**Short-term Memory:**

- Current episode context
- Active conversation history
- Immediate state info

**Long-term Memory:**

- Episodic summaries (all past)
- State history (complete log)
- KG (persistent knowledge)

**Working Memory:**

- Retrieved context
- Current plan
- Reflection results

## Scalability Considerations

1. **Knowledge Graph**
   - Incremental updates
   - Efficient graph traversal
   - Vector index optimization

2. **Memory Management**
   - Sliding window untuk long stories
   - Hierarchical summarization
   - Selective retrieval

3. **Computation**
   - Async operations
   - Batch processing
   - Caching strategies

## References

- LightRAG: Guo et al. (2024)
- Agentic AI / tool-use patterns: lihat literatur terkait pada proposal penelitian
