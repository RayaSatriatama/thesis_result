# Panduan Konfigurasi (*Configuration Guide*)

Proyek ini menggunakan konfigurasi berbasis *Environment Variables* yang dapat diatur melalui file `.env` di direktori *root*. Anda dapat menyalin ` .env.example` menjadi `.env` sebagai langkah awal.

Berikut adalah penjelasan lengkap dari semua parameter dan *settings* yang tersedia dalam sistem Agentic AI dan LightRAG:

## 1. Provider LLM (Language Model)

| Parameter | Deskripsi | Default / Contoh |
|-----------|-----------|------------------|
| `LLM_PROVIDER` | Menentukan platform LLM yang akan digunakan oleh agen (Planner, Writer, Critic, dsb). Pilihan: `google_vertexai`, `google_genai`, `openai`, `openrouter`, `deepseek`, `glm`, `ollama` | `google_vertexai` |
| `LLM_MODEL` | Nama model spesifik yang akan dipanggil. Jika dikosongkan, akan memakai model default dari masing-masing *provider*. | `gemini-2.5-flash` |
| `OPENROUTER_ENABLE_WEB_SEARCH` | Menyalakan server tool web saat `LLM_PROVIDER=openrouter`. Set `false` untuk benchmark gratis; LightRAG tetap digunakan. | `true` |

### Peran evaluator terpisah

Generator dan evaluator dapat memakai model berbeda. Pengaturan berikut hanya
mengubah `CriticAgent`; seluruh agen generator tetap memakai `LLM_PROVIDER` dan
`LLM_MODEL`.

| Variabel | Fungsi |
|---|---|
| `EVALUATOR_PROVIDER` | Provider evaluator, misalnya `openrouter`. Kosong berarti Critic memakai provider global. |
| `EVALUATOR_MODEL` | Slug model evaluator untuk educational, coherence, dan G-Eval. Kosong berarti mengikuti model Critic sebelumnya. |
| `EVALUATOR_RAGAS_MODEL` | Slug evaluator khusus RAGAS/FABLES. Kosong memakai `EVALUATOR_MODEL` jika providernya OpenRouter. |
| `EVALUATOR_OPENROUTER_PROVIDER_PREFERENCES` | Objek JSON `provider` OpenRouter untuk routing evaluator. |

Contoh runtime evaluator terpisah:

```dotenv
LLM_PROVIDER=openrouter
LLM_MODEL=google/gemini-2.5-flash
EVALUATOR_PROVIDER=openrouter
EVALUATOR_MODEL=provider/model-slug
EVALUATOR_RAGAS_MODEL=provider/model-slug
EVALUATOR_OPENROUTER_PROVIDER_PREFERENCES={"allow_fallbacks":false,"require_parameters":true,"data_collection":"deny"}
```

Objek `provider` diteruskan apa adanya ke request OpenRouter. Field yang
didukung meliputi `order`, `allow_fallbacks`, `require_parameters`,
`data_collection`, `zdr`, `only`, `ignore`, `quantizations`, `sort`, batas
harga, serta preferensi throughput atau latency. Untuk hasil benchmark, set
`allow_fallbacks` ke `false`; dengan begitu model provider yang benar-benar
menjawab tidak berubah diam-diam.

Untuk generator utama, gunakan `OPENROUTER_PROVIDER_PREFERENCES` dengan format
objek yang sama. Pengaturan ini dipakai hanya saat `LLM_PROVIDER=openrouter`.
Contoh `{"only":["openai"],"allow_fallbacks":false,"require_parameters":true}`
memaksa `openai/gpt-4o-mini` ke endpoint OpenAI tanpa fallback.

### Benchmark evaluator pada keluaran Gemini yang sudah ada

`scripts/benchmark_openrouter_evaluators.py` membaca observation JSONL dan
menulis artefak baru. Tiga kelompok hasilnya adalah `geval`, `fables`, dan
`ragas`. G-Eval membaca pertanyaan serta cerita final dari observasi
`critic_agent`. RAGAS dan FABLES memakai cerita serta konteks yang sama dari
trace RAGAS. Saat keduanya dipilih, runner memanggil `RagasEvaluator.run()`
satu kali, lalu menulis skor RAGAS dan FABLES yang memang sudah dikembalikan
oleh evaluator tersebut. Tidak ada pipeline FABLES kedua dan skrip tidak
menimpa ekspor sumber. Pelaporan ke Langfuse hanya terjadi bila
`langfuse.enabled` diaktifkan.

Buat konfigurasi eksplisit, dengan slug model tetap. Jangan gunakan
`openrouter/free`, karena router tersebut memilih model berbeda antar request.

Eksekusi evaluator berjalan paralel secara default, dengan paling banyak tiga
model evaluator aktif pada saat yang sama. Atur `execution.parallel` menjadi
`false` untuk menjalankan model satu per satu. Pelaporan Langfuse sepenuhnya
opt-in melalui `langfuse.enabled`; saat `false`, runner tidak membuat trace atau
score baru di Langfuse.

Untuk export historis, mode default `local_export` tidak menulis ke Langfuse.
Runner membuat `trace_overlays/<source-trace-id>.json` di direktori output.
Artefak ini menempatkan `external_benchmark_evaluation` sebagai anak dari root
`StoryGenerationWorkflow`; setiap evaluator menjadi anaknya, dan `geval`,
`fables`, serta `ragas` menjadi anak evaluator. Dengan demikian tiga model
evaluator dapat dibandingkan tanpa mengubah atau membuat ulang trace lama.

Untuk workflow baru, pilih `source_trace` dan aktifkan `langfuse.enabled`.
Mode ini hanya dipakai saat root observation ID dari `StoryGenerationWorkflow`
tersedia. Score ditempelkan ke observation evaluator, sehingga nama score yang
sama tidak bertumpuk pada root trace. `separate_trace` tersedia hanya untuk
kompatibilitas dengan format lama dan tidak direkomendasikan untuk benchmark
yang perlu ditelusuri dari workflow asal.

```json
{
  "source": {"observations_dir": "Eval_Data/Observations"},
  "metrics": ["geval", "fables", "ragas"],
  "execution": {"parallel": true, "max_concurrency": 3},
  "langfuse": {
    "enabled": false,
    "mode": "local_export",
    "session_id_template": "benchmark:{source_trace_id}",
    "trace_name_prefix": "BenchmarkEvaluation",
    "score_config_ids": {
      "geval_coherence_normalized": "langfuse-score-config-id",
      "fables_faithfulness": "langfuse-score-config-id",
      "ragas_standard_faithfulness": "langfuse-score-config-id",
      "ragas_answer_relevancy": "langfuse-score-config-id",
      "ragas_context_relevance": "langfuse-score-config-id"
    }
  },
  "ragas": {
    "embedding_model": "replace-with-an-explicit-embedding-model-slug",
    "require_free": true
  },
  "evaluators": [
    {
      "id": "free-judge",
      "model": "replace-with-current-free-model-slug",
      "temperature": 0.0,
      "require_free": true,
      "provider_preferences": {
        "allow_fallbacks": false,
        "require_parameters": true,
        "data_collection": "deny"
      }
    }
  ]
}
```

Mulai dengan prapenerbangan tanpa inferensi:

```bash
PYTHONPATH=src .venv/bin/python scripts/benchmark_openrouter_evaluators.py \
  --config benchmark.json --output-dir Eval_Data/BenchmarkRuns/free-judge-dry-run --dry-run
```

Prapenerbangan membaca katalog model OpenRouter saat itu dan menolak model
evaluator maupun embedding yang tidak gratis saat `require_free` bernilai
`true`. `ragas.embedding_model` wajib eksplisit untuk RAGAS penuh, sehingga
benchmark tidak dapat diam-diam menggunakan embedding default berbayar.
Tambahkan `--smoke-tools --limit 1` hanya untuk menguji capability tools secara
terpisah. Untuk evaluasi penuh, hilangkan `--dry-run`; hasilnya adalah
`manifest.json`, `results.jsonl`, serta `trace_overlays/` di direktori output
baru. Export sumber tetap tidak berubah.

G-Eval memakai dependency `deepeval==3.9.2` dari `requirements.txt`; runner
menulis baris gagal bila provider tidak mengembalikan skor. FABLES dapat
dijalankan tanpa embedding bila dipilih sendiri, sedangkan RAGAS penuh
memerlukan embedding. Jika model
gratis tidak menyediakan endpoint dengan `data_collection: "deny"`, pilih
`data_collection: "allow"` hanya untuk prompt uji non-sensitif dan catat
keputusan tersebut di artefak benchmark.

**Pengaturan Khusus per Provider:**
- **Vertex AI**: Butuh `GOOGLE_CLOUD_PROJECT` dan `GOOGLE_CLOUD_LOCATION` (serta `credential.json` di root).
- **Google GenAI / DeepSeek / Zhipu / OpenAI**: Butuh *API Key* masing-masing (`GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `GLM_API_KEY`, `OPENAI_API_KEY`).
- **OpenRouter**: `OPENROUTER_API_KEY`, bisa *override* URL via `OPENROUTER_BASE_URL`.
- **Ollama (Lokal)**: Konfigurasi URL via `OLLAMA_BASE_URL` (contoh: `http://localhost:11434/v1`).

## 2. Parameter Pembuatan Cerita (*Story Generation*)

Pengaturan ini mengontrol bagaimana sistem merangkai dan mengevaluasi cerita.

| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `MAX_REVISIONS` | Batas maksimal putaran revisi (loop) antara *Writer* dan *Critic*. | `7` |
| `QUALITY_THRESHOLD` | Ambang batas nilai kelulusan edukasi dari *Critic* (skala 1-5). Cerita harus mencapai nilai ini agar tidak direvisi lagi. | `4.0` |
| `COHERENCE_PENALTY_WEIGHT` | Bobot penalti (*penalty weight*) untuk setiap isu koherensi yang ditemukan oleh Critic. | `1.0` |

### Parameter Spesifik Tiap Agen

Saat ini, parameter lingkungan (`.env`) yang ditujukan secara spesifik untuk masing-masing agen terbagi menjadi dua, yaitu **Temperature** (untuk mengatur tingkat objektivitas vs kreativitas) dan **Feature Flags** (menyalakan/mematikan fitur agen tambahan).

**A. Pengaturan Temperature (0.0 = Deterministik, 1.0 = Kreatif)**

| Agen | Parameter `.env` | Default | Deskripsi Karakteristik |
|---|---|---|---|
| **Parser** | `PARSER_TEMPERATURE` | `0.3` | Sangat logis/kaku untuk mengekstrak dan memformat permintaan user. |
| **Supervisor** | *(Mengikuti Parser)* | `0.3` | Analitis dan deterministik untuk menentukan rute eksekusi (tanpa halusinasi). |
| **Researcher** | `RESEARCHER_TEMPERATURE` | `0.5` | Seimbang dan netral untuk melakukan pencarian fakta/KG. |
| **Diagram** | *(Konstan dalam kode)* | `0.5` | Seimbang untuk menghasilkan struktur diagram alur terpandu. |
| **Planner** | `PLANNER_TEMPERATURE` | `0.7` | Cukup luwes untuk merancang ide dan *outline* awal cerita. |
| **Director** | *(Konstan dalam kode)* | `0.7` | Mengarahkan dan memberi panduan narasi adegan yang menarik. |
| **Writer** | `WRITER_TEMPERATURE` | `0.8` | Tinggi agar penulisan cerita/dialog lebih ekspresif, hidup, dan bervariasi. |
| **Critic** | `CRITIC_TEMPERATURE` | `0.2` | Sangat rendah agar evaluasi/kritik edukasional sangat ketat, konsisten, dan objektif. |

**B. Feature Flags Agen Tambahan**
| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `ENABLE_IMAGE_WRITER` | Mengaktifkan sub-agen penulis untuk generasi *prompt* gambar (butuh OpenRouter). | `false` |
| `ENABLE_DIAGRAM_WRITER`| Mengaktifkan sub-agen untuk menyisipkan diagram Mermaid. | `false` |
| `ENABLE_DIRECTOR` | Mengaktifkan agen pengarah/sutradara (*Director*). | `false` |
| `ENABLE_CRITIC_EVAL_METRICS` | Memaksa metrik evaluasi *Critic* ditampilkan lebih rinci ke *logs*. | `false` |

*(Catatan: Semua agen di atas menggunakan jenis model LLM yang sama secara global seperti yang diatur pada `LLM_MODEL`)*

## 3. LightRAG (Knowledge Graph)

Parameter untuk integrasi *database* pengetahuan dan *retrieval*.

| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `LIGHTRAG_API_URL` | Endpoint API untuk memanggil *service* LightRAG. | `http://localhost:9621` |
| `LIGHTRAG_INGEST_ENABLED` | Mengizinkan workflow menulis sumber ke LightRAG. Default `false`, sehingga benchmark tidak mengubah knowledge base bersama. | `false` |
| `LIGHTRAG_WORKING_DIR` | Direktori tempat LightRAG menyimpan indeks lokal. | `./lightrag_storage` |
| `CHUNK_SIZE` | Ukuran pemotongan dokumen saat menelan (*ingestion*) data. | `1200` |
| `CHUNK_OVERLAP` | Jumlah overlap karakter antar *chunk* agar tidak ada konteks yang terputus. | `100` |

## 4. Observability & Debugging

Pengaturan untuk pemantauan, *logging*, dan integrasi Langfuse (untuk perekaman *trace* LLM).

| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `DEBUG_MODE` / `VERBOSE_LOGGING`| Jika `true`, aplikasi akan mengeluarkan log ekstra ke terminal/konsol. | `false` |
| `LANGFUSE_ENABLED` | Menyalakan integrasi Langfuse untuk memonitor LLM calls. | `false` |
| `LANGFUSE_PUBLIC_KEY` | Public key dari *project* Langfuse Anda. | - |
| `LANGFUSE_SECRET_KEY` | Secret key dari *project* Langfuse Anda. | - |
| `LANGFUSE_HOST` | URL *host* dari *server* Langfuse. | `https://cloud.langfuse.com` |

## 5. Keamanan & Antarmuka UI (API / Gradio)

| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `API_KEY` | Kunci keamanan untuk *request* dari *frontend* ke *backend* API FastAPI. | - |
| `ALLOWED_ORIGINS` | Daftar domain CORS yang diizinkan memanggil API. | `*` |
| `SERVER_PORT` | Port untuk Gradio UI. | `6723` |
| `APP_TITLE` | Judul aplikasi pada UI. | `AI Pembelajaran Berbasis Cerita` |
