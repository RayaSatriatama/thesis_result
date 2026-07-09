# Panduan Konfigurasi (*Configuration Guide*)

Proyek ini menggunakan konfigurasi berbasis *Environment Variables* yang dapat diatur melalui file `.env` di direktori *root*. Anda dapat menyalin ` .env.example` menjadi `.env` sebagai langkah awal.

Berikut adalah penjelasan lengkap dari semua parameter dan *settings* yang tersedia dalam sistem Agentic AI dan LightRAG:

## 1. Provider LLM (Language Model)

| Parameter | Deskripsi | Default / Contoh |
|-----------|-----------|------------------|
| `LLM_PROVIDER` | Menentukan platform LLM yang akan digunakan oleh agen (Planner, Writer, Critic, dsb). Pilihan: `google_vertexai`, `google_genai`, `openai`, `openrouter`, `deepseek`, `glm`, `ollama` | `google_vertexai` |
| `LLM_MODEL` | Nama model spesifik yang akan dipanggil. Jika dikosongkan, akan memakai model default dari masing-masing *provider*. | `gemini-2.5-flash` |

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
