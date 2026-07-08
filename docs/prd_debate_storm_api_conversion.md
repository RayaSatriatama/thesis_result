# PRD: Konversi Notebook Debate & STORM ke Script Modular dengan Akses API (ADDIE-Adapted)

**Dokumen**: Product Requirements Document (PRD)
**Versi**: 1.0.0
**Tanggal**: 2026-06-17
**Status**: Draft
**Peneliti**: Mohammad Raya Satriatama (NIM: 2206418)

---

## 1. Latar Belakang & Konteks

### 1.1 Situasi Saat Ini

Proyek skripsi ini mengimplementasikan sistem **Agentic AI** untuk pembelajaran berbasis cerita (*story-based learning*) menggunakan kerangka **ADDIE** (Analysis, Design, Development, Implementation, Evaluation) sebagai dasar orkestrasi multi-agen. Komponen utamanya adalah `story_agent` -- pipeline LangGraph multi-agen (Planner, Researcher, Writer, Critic, Director) -- yang sudah terekspos via FastAPI.

Dua arsitektur alternatif -- **Debate** (Du et al., 2023) dan **STORM** (Shao et al., 2024) -- saat ini hanya tersedia sebagai notebook eksploratif:

| Notebook | Lokasi | Status |
|---|---|---|
| `multi_agent_debate.ipynb` | `src/workflows/story_agent_debate/` | Notebook saja |
| `multi_agent_storm.ipynb` | `src/workflows/story_agent_storm/` | Notebook saja |

Kedua notebook bergantung pada library `agentic_architectures` (package internal). Pola konversi notebook ke script sudah ada -- `arch_blackboard` sudah dikonversi penuh dan terintegrasi ke router API (`/api/workflow/generate-blackboard`).

### 1.2 Motivasi

1. **Reproducibility eksperimen**: Notebook tidak dapat dipanggil secara programatik dalam pipeline evaluasi batch.
2. **Integrasi ablation study**: Debate dan STORM perlu dikomparasi dengan kondisi eksperimen lain (Single Agent, Blackboard, Multi-Agent utama) via endpoint yang seragam.
3. **Konsistensi ADDIE**: Tahap *Development* dalam ADDIE membutuhkan komponen yang dapat dipanggil via API sehingga `story_agent` (sebagai agen utama) dapat mengorkestrasikan atau mengevaluasi output dari Debate/STORM secara programatik.
4. **Observability**: Semua eksekusi harus tercatat di Langfuse dengan format trace yang seragam (seperti Blackboard).

### 1.3 Referensi Arsitektur yang Sudah Ada

Pola konversi yang diikuti adalah `arch_blackboard`:

```
src/workflows/arch_blackboard/
    __init__.py          # public API: create_blackboard_workflow()
    graph.py             # wrapper: _build_llm(), TraceableBlackboard, create_*_workflow()
    state.py             # TypedDict state: library fields + API wrapper fields
    prompts.py           # konstanta prompt (auditable, tidak dimodifikasi)
```

Router API-nya di `src/apps/api/routers/workflow.py` menggunakan pola:
- Singleton lazy-init `_get_*_workflow()`
- SSE stream generator `generate_*_sse_stream()`
- FastAPI endpoint `@router.post("/generate-*")`

### 1.4 Referensi Paper

| Paper | Temuan Kunci yang Relevan |
|---|---|
| Du et al. (2023). *Improving Factuality and Reasoning in LLMs through Multiagent Debate*. [arXiv:2305.14325](https://arxiv.org/abs/2305.14325) | (1) 3 agen + 2 ronde optimal untuk cost-accuracy tradeoff; (2) Debate meningkatkan akurasi GSM8K dari 77% (single) ke 85% (debate); (3) Agen "agreeable" karena RLHF -- persona berbeda meningkatkan MMLU dari 71.1% ke 74.2%; (4) Konvergensi diindikasikan oleh `round_unique_answer_count` |
| Shao et al. (2024). *Assisting in Writing Wikipedia-like Articles From Scratch with LLMs*. [arXiv:2402.14207](https://arxiv.org/abs/2402.14207) | (1) Pre-writing stage (perspektif + Q&A + outline) adalah kunci -- ablasi tanpa outline menurunkan semua metrik signifikan; (2) Perspektif-guided question asking mengungguli direct prompting dalam heading soft recall; (3) Simulated conversation (iterative) jauh lebih baik dari one-shot question generation; (4) Web search grounding wajib untuk factuality |

---

## 2. Tujuan & Sasaran

### 2.1 Tujuan Utama

Mengkonversi notebook `multi_agent_debate.ipynb` dan `multi_agent_storm.ipynb` menjadi modul Python yang dapat diakses via REST API, dengan pola yang konsisten dengan `arch_blackboard` yang sudah ada.

### 2.2 Sasaran Terukur

| Sasaran | Kriteria Sukses |
|---|---|
| Script Debate berjalan | `from workflows.story_agent_debate.graph import create_debate_workflow` berhasil diimpor |
| Script STORM berjalan | `from workflows.story_agent_storm.graph import create_storm_workflow` berhasil diimpor |
| Endpoint Debate aktif | `POST /api/workflow/generate-debate` mengembalikan SSE stream |
| Endpoint STORM aktif | `POST /api/workflow/generate-storm` mengembalikan SSE stream |
| Langfuse terintegrasi | Trace muncul di Langfuse dengan `workflow_mode="debate"` / `"storm"` |
| Skema SSE seragam | Event format sama dengan endpoint lain: `WORKFLOW::MULAI`, `WORKFLOW::SELESAI`, `WORKFLOW::GALAT` |
| Metadata paper-aligned | Debate: `convergence`, `round_unique_answer_count`, `final_tally` sesuai Du et al. §3.3; STORM: `n_perspectives`, `n_questions`, `outline` sesuai Shao et al. §3 |

---

## 3. Pemetaan ADDIE ke Komponen

Penelitian ini mengadaptasi model ADDIE sebagai *subject* orkestrasi multi-agen dengan `story_agent` sebagai agen utama:

| Fase ADDIE | Peran dalam Sistem | Komponen Terkait |
|---|---|---|
| **Analysis** | Analisis kebutuhan konten & target peserta didik | `SupervisorAgent` + `ResearchAgent` (LightRAG query) |
| **Design** | Perancangan alur narasi, karakter, struktur | `PlannerAgent` (outline, moral, active_writers) |
| **Development** | Produksi konten cerita multi-format | `WriterAgent`, `WriterDiagramAgent`, `ImageGeneratorAgent`, **Debate**, **STORM** |
| **Implementation** | Penyajian konten via API/UI | FastAPI endpoints, SSE streaming, Streamlit UI |
| **Evaluation** | Evaluasi kualitas dan faithfulness | `CriticAgent` (GEval + RAGAS + FABLES) + Langfuse |

### 3.1 Adaptasi ADDIE ke Debate (Du et al., 2023)

Dalam konteks ADDIE, Debate mengadaptasi fase *Development* dengan pendekatan *Society of Mind* (Minsky, 1988):

| Sub-Fase ADDIE Development | Padanan Debate |
|---|---|
| Pemilihan strategi instruksional | Pemilihan persona agen (professor, doctor, mathematician -- Du et al. §3.3 analysis) |
| Produksi konten awal | Round 1: setiap agen menjawab secara independen (tanpa cross-talk) |
| Review & revisi konten | Round 2+: setiap agen membaca jawaban agen lain dan memperbarui response-nya |
| Validasi konten | Voting mayoritas (`Counter.most_common(1)`) sebagai mekanisme seleksi jawaban terbaik |

**Implikasi implementasi**: Task yang dikirim ke Debate adalah *topik pembelajaran* dalam framing ADDIE (mis. "Jelaskan konsep X untuk usia 8-12 tahun"), bukan sekadar pertanyaan faktual. Agen mendebat cara terbaik menjelaskan konsep tersebut.

**Insight paper untuk prompt**: Du et al. §3.3 membuktikan bahwa persona berbeda ("stubborn" vs "agreeable") menghasilkan durasi debate berbeda. Prompt yang mendorong agen untuk mempertahankan argumen lebih lama menghasilkan jawaban final lebih akurat. Default `Debate.AGENT_PERSONAS` dari library sudah mengikuti prinsip ini.

### 3.2 Adaptasi ADDIE ke STORM (Shao et al., 2024)

STORM secara struktural paling dekat dengan keseluruhan siklus ADDIE karena pipeline 5-tahapnya memetakan langsung:

| Tahap STORM | Fase ADDIE Padanan | Proses |
|---|---|---|
| **Perspectives** (tahap 1) | Analysis | Identifikasi sudut pandang pemangku kepentingan (Shao et al. §3.1: "diverse perspectives lead to varied questions") |
| **Questions** (tahap 2) | Analysis + Design | Simulated conversation -- writer-agen bertanya, expert-agen menjawab berdasarkan web search (§3.2) |
| **Answer/Research** (tahap 3) | Analysis | Web retrieval + synthesis untuk setiap pertanyaan; grounding factuality |
| **Outline** (tahap 4) | Design | Draft outline dari LLM knowledge, lalu *refine* dengan conversation history (§3.3) |
| **Write** (tahap 5) | Development | Penulisan section-by-section menggunakan outline + references (§3.4) |

**Implikasi implementasi**: Topic yang dikirim ke STORM harus diframing sebagai *topik konten pembelajaran* ADDIE (mis. "Pengembangan kurikulum berbasis AI"). Pipeline STORM secara alami menghasilkan artikel terstruktur yang bisa menjadi *bahan ajar* yang sudah melewati fase Analysis dan Design.

**Insight paper kritis**: Shao et al. ablation study (§5.2) membuktikan bahwa:
1. Menghapus outline stage menurunkan semua metrik secara signifikan -- outline *wajib*
2. Menghapus perspective-guided question asking menurunkan kualitas outline
3. Menghapus simulated conversation (one-shot questions) adalah ablasi terburuk -- iterative Q&A adalah inti STORM

Ini berarti web search (`web_search_fn`) tidak boleh di-skip karena grounding answers adalah syarat agar iterative conversation bermakna.

---

## 4. Spesifikasi Teknis

### 4.1 Struktur Direktori Target

```
src/workflows/story_agent_debate/
    __init__.py              # public API
    graph.py                 # DebateWorkflow wrapper + create_debate_workflow()
    state.py                 # DebateWrapperState TypedDict
    prompts.py               # AGENT_PERSONAS (auditable copy dari library)

src/workflows/story_agent_storm/
    __init__.py              # public API
    graph.py                 # StormWorkflow wrapper + create_storm_workflow()
    state.py                 # StormWrapperState TypedDict
    prompts.py               # default config constants (n_perspectives, etc.)
```

### 4.2 Module: `story_agent_debate`

#### 4.2.1 `graph.py`

```
Fungsi utama:
    _build_llm()                  -- sama dengan pola blackboard, baca LLMProviderConfig
    create_debate_workflow()      -- return TraceableDebate instance
                                     n_agents=3, n_rounds=2 (Du et al. §3: default optimal)
                                     sample_temperature=0.7 (untuk diversity jawaban awal)

Class:
    TraceableDebate(Debate)       -- subclass dari agentic_architectures.Debate
                                     override run() agar mendukung callbacks + metadata output
                                     output ArchitectureResult dengan metadata:
                                       - convergence (bool) -- apakah semua agen sepakat
                                       - final_tally (dict) -- Counter.most_common(1) Du et al. §2.1
                                       - round_unique_answer_count (list[int]) -- indikator divergensi
                                       - rounds (list: per-agent answer + critique_of_others)
                                     CATATAN: _DebateResponse schema memerlukan field
                                     "answer" DAN "critique_of_others" per agent per round
                                     (bukan hanya jawaban) -- ini enforcement dari paper §2.1
                                     "require both answer AND critique" untuk mencegah restating
```

#### 4.2.2 `state.py`

```
DebateWrapperState(TypedDict, total=False):
    # Library fields (dari Debate internal state)
    task: str
    rounds: list         -- per-round agent responses
    final_answer: str    -- majority-voted answer
    convergence: bool

    # API wrapper fields
    workflow_mode: str   -- selalu "debate"
    language: str
    theme: str
    session_id: str
    trace_id: str
```

#### 4.2.3 `prompts.py`

Salinan verbatim `Debate.AGENT_PERSONAS` dari library (3 persona default). Tidak dimodifikasi -- ini adalah controlled baseline.

### 4.3 Module: `story_agent_storm`

#### 4.3.1 `graph.py`

```
Fungsi utama:
    _build_llm()                   -- sama dengan pola blackboard
    _build_web_search_fn()         -- bungkus web_search_tool(max_results=3) dari library
                                      Shao et al. §3.2: web search wajib untuk grounding
                                      answers dalam simulated conversation
                                      Graceful degradation jika Tavily tidak tersedia:
                                        return ["(web search unavailable)"] -- pipeline tetap
                                        berjalan tapi kualitas outline menurun
    create_storm_workflow()        -- return TraceableSTORM instance
                                     n_perspectives=3 (Shao et al. §4.4: N=5 di paper,
                                       dikurangi ke 3 di notebook untuk cost)
                                     questions_per_perspective=2 (M=5 di paper, dikurangi
                                       ke 2 di notebook)

Class:
    TraceableSTORM(STORM)          -- subclass dari agentic_architectures.STORM
                                     override run() agar mendukung callbacks + metadata output
                                     output ArchitectureResult dengan metadata:
                                       - n_perspectives (int) -- Shao et al. §3.1
                                       - n_questions (int)    -- total Q across all perspectives
                                       - n_sections (int)     -- outline sections §3.3
                                       - article_chars (int)  -- output length §3.4
                                       - perspectives (list[str]) -- discovered perspectives
                                       - questions (list[dict])   -- per-perspective Q&A
                                       - outline (list[dict])     -- refined outline §3.3
                                     CATATAN: outline HARUS ada (bukan opsional).
                                     Shao et al. ablation (§5.2) membuktikan outline stage
                                     wajib -- tanpanya semua metrik turun signifikan.
```

#### 4.3.2 `state.py`

```
StormWrapperState(TypedDict, total=False):
    # Library fields
    task: str
    perspectives: list[str]
    questions: list[dict]
    answers: list[dict]
    outline: list[dict]
    article: str

    # API wrapper fields
    workflow_mode: str   -- selalu "storm"
    language: str
    theme: str
    session_id: str
    trace_id: str
```

#### 4.3.3 `prompts.py`

Konstanta konfigurasi default: `DEFAULT_N_PERSPECTIVES = 3`, `DEFAULT_QUESTIONS_PER_PERSPECTIVE = 2`. Ini adalah controlled baseline.

### 4.4 API Endpoints

Ditambahkan ke `src/apps/api/routers/workflow.py`:

#### Endpoint Debate

```
POST /api/workflow/generate-debate
Content-Type: application/json
Authorization: X-API-Key <key>

Request body: WorkflowRequest (sama dengan endpoint lain)
    prompt: str           -- task/pertanyaan yang di-debate
    target_age: str       -- opsional, disertakan dalam task prompt
    language: str         -- "Indonesian" | "English"
    story_length: str     -- opsional, diabaikan oleh Debate

Response: text/event-stream (SSE)

Events yang dikirim:
    WORKFLOW::MULAI              -- job dimulai, job_id
    DEBATE::MULAI                -- arsitektur mulai, task preview
    DEBATE::RONDE                -- satu ronde selesai, agent responses
    WORKFLOW::SELESAI            -- output final, metadata convergence
    WORKFLOW::GALAT              -- error
```

#### Endpoint STORM

```
POST /api/workflow/generate-storm
Content-Type: application/json
Authorization: X-API-Key <key>

Request body: WorkflowRequest (sama)

Response: text/event-stream (SSE)

Events yang dikirim:
    WORKFLOW::MULAI              -- job dimulai, job_id
    STORM::MULAI                 -- pipeline mulai
    STORM::PERSPEKTIF            -- perspectives selesai dihasilkan
    STORM::PERTANYAAN            -- questions per perspective selesai
    STORM::OUTLINE               -- outline artikel selesai
    WORKFLOW::SELESAI            -- artikel final + metadata pipeline
    WORKFLOW::GALAT              -- error
```

### 4.5 Skema SSE `WORKFLOW::SELESAI` -- Debate

```json
{
    "job_id": "debate_<hex12>",
    "mode": "debate",
    "final_story": "<majority-voted answer>",
    "draft_title": "",
    "quality_score": 0.0,
    "revision_count": 0,
    "elapsed_time": 12.4,
    "metadata": {
        "convergence": true,
        "final_tally": {"1": 3},
        "round_unique_answer_count": [2, 1],
        "n_agents": 3,
        "n_rounds": 2
    }
}
```

### 4.6 Skema SSE `WORKFLOW::SELESAI` -- STORM

```json
{
    "job_id": "storm_<hex12>",
    "mode": "storm",
    "final_story": "<artikel lengkap>",
    "draft_title": "",
    "quality_score": 0.0,
    "revision_count": 0,
    "elapsed_time": 87.2,
    "metadata": {
        "n_perspectives": 3,
        "n_questions": 6,
        "n_sections": 4,
        "article_chars": 5000,
        "perspectives": ["...", "...", "..."],
        "outline": [{"title": "...", "key_points": [...]}]
    }
}
```

### 4.7 Singleton & Warmup

Di `workflow.py` ditambahkan:

```python
_debate_workflow_instance = None
_storm_workflow_instance = None

def _get_debate_workflow():
    global _debate_workflow_instance
    if _debate_workflow_instance is None:
        _debate_workflow_instance = create_debate_workflow()
    return _debate_workflow_instance

def _get_storm_workflow():
    global _storm_workflow_instance
    if _storm_workflow_instance is None:
        _storm_workflow_instance = create_storm_workflow()
    return _storm_workflow_instance
```

Kedua singleton tidak dimasukkan ke pre-warmup lifespan (biaya init minimal, tidak mau menambah latency startup).

### 4.8 Integrasi Langfuse

Pola yang sama dengan Blackboard dan Single Agent:

```python
trace_wrapper = langfuse.trace(
    name="DebateWorkflow",   # atau "StormWorkflow"
    session_id=job_id,
    user_id=getattr(request, "user_id", "user_v1"),
    input_data=request.prompt,
    metadata={
        "job_id": job_id,
        "workflow_mode": "debate",   # atau "storm"
        "target_age": request.target_age,
        "theme": request.prompt,
    }
)
```

---

## 5. Perubahan File

### 5.1 File Baru

| File | Deskripsi |
|---|---|
| `src/workflows/story_agent_debate/__init__.py` | Public API: `create_debate_workflow` |
| `src/workflows/story_agent_debate/graph.py` | `TraceableDebate`, `create_debate_workflow()`, `_build_llm()` |
| `src/workflows/story_agent_debate/state.py` | `DebateWrapperState` TypedDict |
| `src/workflows/story_agent_debate/prompts.py` | `AGENT_PERSONAS` (verbatim copy) |
| `src/workflows/story_agent_storm/__init__.py` | Public API: `create_storm_workflow` |
| `src/workflows/story_agent_storm/graph.py` | `TraceableSTORM`, `create_storm_workflow()`, `_build_llm()`, `_build_web_search_fn()` |
| `src/workflows/story_agent_storm/state.py` | `StormWrapperState` TypedDict |
| `src/workflows/story_agent_storm/prompts.py` | `DEFAULT_N_PERSPECTIVES`, `DEFAULT_QUESTIONS_PER_PERSPECTIVE` |

### 5.2 File Dimodifikasi

| File | Perubahan |
|---|---|
| `src/apps/api/routers/workflow.py` | Tambah import Debate/STORM, singleton `_get_*`, SSE generators, 2 endpoint baru |
| `src/apps/api/main.py` | Update `agents_available` di health response (jika diperlukan) |
| `docs/index.md` | Tambah entry untuk endpoint baru |
| `README.md` | Tambah dokumentasi endpoint `/generate-debate` dan `/generate-storm` |

### 5.3 File Tidak Dimodifikasi

- Semua file di `src/workflows/story_agent/` -- pipeline utama tidak berubah
- `src/apps/api/schemas.py` -- `WorkflowRequest` sudah cukup untuk kedua endpoint
- `src/settings.py` -- tidak ada konfigurasi baru yang dibutuhkan

---

## 6. Perbedaan dari Blackboard

| Aspek | Blackboard (C4) | Debate (baru) | STORM (baru) |
|---|---|---|---|
| Library class | `Blackboard` | `Debate` | `STORM` |
| Execution | Sync `arch.run()` via `asyncio.to_thread` | Sync via `asyncio.to_thread` | Sync via `asyncio.to_thread` |
| Web search | Tidak ada | Tidak ada | Ya (Tavily, opsional) |
| Output utama | Synthesized essay | Majority-voted answer | Multi-section article |
| Metadata kunci | `total_rounds`, `agents_who_contributed` | `convergence`, `final_tally`, `round_unique_answer_count` | `n_perspectives`, `n_questions`, `n_sections`, `outline` |
| SSE event kustom | `BLACKBOARD::KONTRIBUSI` | `DEBATE::RONDE` | `STORM::PERSPEKTIF`, `STORM::OUTLINE` |
| Langfuse trace name | `"BlackboardWorkflow"` | `"DebateWorkflow"` | `"StormWorkflow"` |
| `workflow_mode` | `"blackboard"` | `"debate"` | `"storm"` |

---

## 7. Pertimbangan Web Search pada STORM

STORM membutuhkan `web_search_fn` untuk fase *answer* (menjawab pertanyaan per perspektif dengan referensi eksternal). Ini bukan fitur opsional -- Shao et al. (2024) §3.2 menunjukkan bahwa grounding answers pada trusted Internet sources adalah syarat agar simulated conversation menghasilkan outline yang lebih baik dari direct generation.

Ablas study Shao et al. §5.2 (Tabel 5) menunjukkan bahwa tanpa simulated conversation (web search), jumlah unique references `|R|` turun dari 99.83 ke 39.56 -- penurunan 60% yang langsung mempengaruhi kualitas artikel.

Implementasi:

1. **Tavily tersedia** (`TAVILY_API_KEY` di env): Gunakan `web_search_tool(max_results=3)` dari library -- perilaku persis sama dengan notebook.
2. **Tavily tidak tersedia**: Graceful degradation -- `web_search_fn` mengembalikan `["(web search unavailable)"]` tanpa crash. Pipeline tetap berjalan dengan knowledge parametrik LLM saja (seperti `Direct Gen` baseline di paper -- lebih lemah tapi valid).

> **Catatan**: Tidak ada fallback logic yang diciptakan baru -- ini mereplikasi fallback eksplisit yang sudah ada di notebook.

### 7.1 Pertimbangan Debate: Persona sebagai Proxy Perspektif ADDIE

Du et al. §3.3 menunjukkan bahwa menggunakan persona berbeda (professor, doctor, mathematician) pada MMLU meningkatkan akurasi dari 71.1% ke 74.2%. Untuk konteks ADDIE:

- Default `Debate.AGENT_PERSONAS` dari library (3 persona generik) digunakan sebagai controlled baseline.
- Jika di masa depan ingin membuat kondisi eksperimen terpisah dengan persona ADDIE-adapted (mis. "curriculum designer", "subject matter expert", "learner representative"), buat file `prompts_addie_adapted.py` terpisah dan dokumentasikan sebagai kondisi eksperimen berbeda -- JANGAN modifikasi `prompts.py` yang merupakan controlled baseline.

---

## 8. Constraints & Risiko

### 8.1 Constraints

- Maksimum 1000 baris per file -- jika `workflow.py` melebihi batas, ekstrak SSE generators ke file terpisah (`routers/workflow_debate.py`, `routers/workflow_storm.py`).
- Tidak memodifikasi library `agentic_architectures` -- hanya subclassing.
- Semua prompt constants harus disimpan di `prompts.py` masing-masing modul (auditable untuk eksperimen).

### 8.2 Risiko

| Risiko | Probabilitas | Mitigasi |
|---|---|---|
| `agentic_architectures.Debate` tidak support `callbacks` | Sedang | Sama dengan Blackboard -- bungkus `.run()` secara manual tanpa callbacks |
| STORM sangat lambat (12+ LLM calls) | Tinggi | SSE streaming memberikan feedback progresif; timeout tidak menjadi masalah |
| Tavily rate limit di batch eval | Sedang | Gunakan `max_results=3`, tambah `time.sleep(0.5)` antar panggilan jika diperlukan |
| `workflow.py` melebihi 1000 baris | Tinggi | Saat ini ~670 baris + ~150 per workflow baru = ~970 baris; perlu dipantau |

---

## 9. Verification Plan

### 9.1 Tes Unit Minimal

Tambahkan di `tests/`:

```
tests/test_debate_workflow.py
    - test_create_debate_workflow_instantiation()
    - test_debate_state_schema()

tests/test_storm_workflow.py
    - test_create_storm_workflow_instantiation()
    - test_storm_state_schema()
    - test_web_search_fallback()
```

### 9.2 Tes Integrasi API

Gunakan `scripts/run_api_tests.py` yang sudah ada, tambahkan:

```python
# Test /api/workflow/generate-debate
response = requests.post(
    "http://localhost:8000/api/workflow/generate-debate",
    json={"prompt": "Apakah AI akan menggantikan guru?", "language": "Indonesian"},
    headers={"X-API-Key": API_KEY},
    stream=True
)
# Verifikasi: WORKFLOW::MULAI, DEBATE::MULAI, WORKFLOW::SELESAI diterima

# Test /api/workflow/generate-storm
response = requests.post(
    "http://localhost:8000/api/workflow/generate-storm",
    json={"prompt": "Pengembangan kurikulum berbasis AI di Indonesia", "language": "Indonesian"},
    headers={"X-API-Key": API_KEY},
    stream=True
)
# Verifikasi: WORKFLOW::MULAI, STORM::MULAI, STORM::PERSPEKTIF, WORKFLOW::SELESAI diterima
```

### 9.3 Verifikasi Manual

1. Jalankan API server: `SYSTEM_LANGUAGE=id uvicorn src.apps.api.main:app --port 8000`
2. Akses Swagger UI: `http://localhost:8000/docs`
3. Verifikasi endpoint `/api/workflow/generate-debate` dan `/api/workflow/generate-storm` muncul di docs
4. Periksa Langfuse dashboard -- trace `DebateWorkflow` dan `StormWorkflow` harus muncul

---

## 10. Urutan Implementasi

Implementasi dilakukan dalam urutan berikut agar dapat ditest secara inkremental:

```
Fase 1: Debate Script
    1.1  src/workflows/story_agent_debate/prompts.py
    1.2  src/workflows/story_agent_debate/state.py
    1.3  src/workflows/story_agent_debate/graph.py
    1.4  src/workflows/story_agent_debate/__init__.py
    1.5  Tambah import + singleton + SSE generator + endpoint Debate ke workflow.py

Fase 2: STORM Script
    2.1  src/workflows/story_agent_storm/prompts.py
    2.2  src/workflows/story_agent_storm/state.py
    2.3  src/workflows/story_agent_storm/graph.py
    2.4  src/workflows/story_agent_storm/__init__.py
    2.5  Tambah import + singleton + SSE generator + endpoint STORM ke workflow.py

Fase 3: Verifikasi & Dokumentasi
    3.1  Jalankan tes unit
    3.2  Jalankan tes integrasi API
    3.3  Update README.md
    3.4  Update docs/index.md
```

---

## 11. Referensi

| Referensi | Keterangan |
|---|---|
| Du et al. (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate*. [arXiv:2305.14325](https://arxiv.org/abs/2305.14325) | Landasan teori Debate |
| Shao et al. (2024). *STORM: Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking*. [arXiv:2402.14207](https://arxiv.org/abs/2402.14207) | Landasan teori STORM |
| `src/workflows/arch_blackboard/graph.py` | Pola konversi yang diikuti |
| `src/apps/api/routers/workflow.py` | Pola router SSE yang diikuti |
| `src/workflows/story_agent_debate/multi_agent_debate.ipynb` | Notebook sumber Debate |
| `src/workflows/story_agent_storm/multi_agent_storm.ipynb` | Notebook sumber STORM |
