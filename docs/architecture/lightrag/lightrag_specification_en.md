# Spesifikasi LightRAG - Sistem Bahasa Inggris (EN)

> **Lokasi:** `docs/architecture/lightrag/lightrag_specification_en.md` · [Versi ID](lightrag_specification_id.md) · [Integrasi utama](../lightrag_integration.md) · [Indeks docs](../../index.md)

Dokumen ini berisi spesifikasi teknis dan parameter lengkap terkait implementasi sistem LightRAG khusus untuk **Bahasa Inggris (EN)** yang digunakan dalam studi "Analisis Kinerja Koherensi Naratif dan Faithfulness pada Sistem Agentic AI dan LightRAG untuk Pembelajaran Berbasis Cerita".

## 1. Teknologi Database (Database Tech Stack)
Sistem LightRAG untuk EN telah dikonfigurasi menggunakan cluster terpisah dari node memory standar, guna efektivitas komputasi pada volume data yang besar. Referensi Workspace untuk keseluruhan stack EN adalah `en`.

*   **Graph Storage (Knowledge Graph):** Neo4J *(Kustom; Default LightRAG: NetworkXStorage)*
    *   **Class:** `Neo4JStorage`
    *   **Koneksi:** `bolt://neo4j:7687` (Docker/Remote)
    *   **Workspace:** `en`
    *   **Parameter Tambahan:**
        *   MAX_CONNECTION_POOL_SIZE: 100 *(Kustom)*
        *   CONNECTION_TIMEOUT: 30s *(Kustom)*
*   **Vector Storage (Vector Database):** Qdrant *(Kustom; Default LightRAG: NanoVectorDBStorage)*
    *   **Class:** `QdrantVectorDBStorage`
    *   **Koneksi:** `http://qdrant:6333`
    *   **Workspace:** `en`
*   **Key-Value (KV) Storage:** Redis *(Kustom; Default LightRAG: JsonKVStorage)*
    *   **Class:** `RedisKVStorage`
    *   **Koneksi:** `redis://redis:6379`
    *   **Workspace:** `en`
*   **Document Status Storage:** Redis *(Kustom; Default LightRAG: JsonDocStatusStorage)*
    *   **Class:** `RedisDocStatusStorage`
    *   **Koneksi:** `redis://redis:6379`

## 2. Spesifikasi Model Machine Learning
Implementasi LLM dan Embedding menggunakan API dari OpenRouter (OpenAI Compatible API).

*   **Model Bahasa (LLM Generation):**
    *   **Model:** `google/gemini-2.5-flash-lite` *(Kustom)*
    *   **Binding:** `openai`
*   **Model Embedding:**
    *   **Model:** `google/gemini-embedding-001` *(Kustom)*
    *   **Binding:** `openai`
    *   **Dimensi Vektor:** 1536
    *   **Token Limit:** 16384
    *   **Time Out:** 30s
    *   **Concurrency Config:**
        *   EMBEDDING_FUNC_MAX_ASYNC: 16 *(Kustom, dioptimasi)*
        *   EMBEDDING_BATCH_NUM: 12 *(Kustom, dioptimasi)*

## 3. Parameter Konfigurasi Klien (story-agent / Node)
Proses menelan teks (ingestion) dan permintaan pencarian (query/retrieval) mematuhi batasan di level *client* berikut ini:

*   **URL Server LightRAG:** `http://100.68.196.58:9621` (Remote) atau `http://localhost:9621` (Local)
*   **LightRAG Ingest Parameters:**
    *   `CHUNK_SIZE`: 1200 *(Default LightRAG)*
    *   `CHUNK_OVERLAP`: 100 *(Default LightRAG)*
    *   `LIGHTRAG_SELECTIVE_INGESTION`: `true` *(Kustom; Hanya resource relevan yang ditelan)*
    *   `LIGHTRAG_INGEST_MIN_LENGTH`: 800 karakter *(Kustom; Filter limit page minimum)*
*   **LightRAG Query Parameters:**
    *   `DEFAULT_MODE`: `hybrid` *(Default LightRAG)*
    *   `TOP_K`: 5 *(Default LightRAG)*

## 4. Status Data & Hasil Injeksi Awal (Initial Ingestion)
Sistem Bahasa Inggris telah diinjeksi 100 konteks dari dataset evaluasi _WikiEval-100_ ("context1" dan "context2"). Status data yang masuk saat injeksi terakhir:

*   **Statistik Knowledge Graph (Neo4J)**
    *   **Jumlah Nodes:** 1530 nodes
    *   **Jumlah Edges (Relasi):** 1487 edges

Database ter-backup statis di `data/backups/rag_storage_20260309_074128_wikieval100_injected/lightrag-en/`. Berisikan ekspor:
1.  **VDB (`vdb_*.json`)** untuk snapshot Vektor.
2.  **KV (`kv_store_*.json`)** untuk teks sepotong (chunk), relasi utuh, dan status doc dari cache redis `en`.
3.  **GraphML (`graph_chunk_entity_relation.graphml`)** untuk graf representasi entitas dan relasi Neo4J `en`.

## 5. Mekanisme Komunikasi (Client-Server)
Mekanisme pengaksesan fitur ke server LightRAG (via `lightrag_client.py`):
*   **Endpoint Health:** `GET /health`
*   **Endpoint Text Ingest:** `POST /documents/text` (`{ "text": "str", "file_source": "str" }`)
*   **Endpoint Retrieval Query:** `POST /query` (Mendukung query parameter: `only_need_context` boolean jika LLM responsif tidak ingin dieksekusi Server RAG).
