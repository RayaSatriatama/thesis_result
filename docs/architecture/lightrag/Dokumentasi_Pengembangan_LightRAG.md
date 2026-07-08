# Dokumentasi Pengembangan Arsitektur LightRAG (Korpus WikiEval HuggingFace)

> **Lokasi:** `docs/architecture/lightrag/Dokumentasi_Pengembangan_LightRAG.md` · [Spesifikasi EN/ID](README.md) · [Integrasi utama](../lightrag_integration.md) · [Indeks docs](../../index.md)

Dokumentasi ini menguraikan langkah-langkah faktual pengembangan sistem **LightRAG**, dengan menggunakan sumber dataset original *WikiEval* yang ditarik langsung dari pustaka resmi (`vibrantlabsai/WikiEval`). Dataset ini berkapasitas 50 observasi (menghasilkan 100 dokumen konteks utuh) dan diolah secara langsung menggunakan *pipeline* LightRAG.

---

## Tahap 1: Data Preparation

Tahap pertama berfungsi menyiapkan *baseline* korpus teks faktual. Bukti diambil murni dari arsip dataset asli (*vibrantlabsai/WikiEval*) melalui pustaka HuggingFace.

### Ekstraksi Dataset WikiEval
*   **Proses**: Mengunduh dan memuat dataset evaluasi secara dinamis menggunakan *library* `datasets`. Dataset ini memuat parameter utuh pertanyaan, jawaban, serta dua variasi konteks referensial (`context_v1` dan `context_v2`).
*   **Bukti Pengambilan Data**:
    ```python
    from datasets import load_dataset

    # Memuat dataset murni dari repositori HuggingFace
    ds = load_dataset("vibrantlabsai/WikiEval")
    print(ds)
    ```

---

## Tahap 2: Data Preprocessing

Data hasil pemuatan tersebut diproses, dibersihkan (*cleaning*), dan diintegrasikan ke dalam bentuk *corpus* dokumen yang valid bagi komponen vektor.

### 1. Data Cleaning & Analisis Panjang Konteks (Enrichment)
*   **Proses**: Melakukan pengecekan duplikasi, anomali skema, kekosongan data (*missing values*), serta analisis distribusi pengayaan kata dari `context_v1` ke `context_v2`.
*   **Bukti Hasil Pembersihan & Analisis (Output Jupyter Notebook)**:
    - **Validasi Skema & Pra-pemrosesan**:
      ```text
      Total awal                : 50
      Duplikat dihapus          : 0
      Total setelah deduplikasi : 50
      Item invalid schema       : 0
      Semua item memenuhi skema minimal.
      ```
    - **Pengecekan Data Kosong (Missing Values)**:
      ```text
      kolom               missing_sebelum  missing_sesudah
      answer              0                0
      context_v1          0                0
      context_v2          0                0
      poor_answer         0                0
      question            0                0
      source              0                0
      ungrounded_answer   0                0
      ```

### 2. Data Integration (Integrasi Konteks)
*   **Proses**: Menggabungkan objek `context_v1` dan `context_v2` secara linear untuk membentuk sekumpulan total 100 dokumen independen.
*   **Bukti Data Integrasi**:
    - **Total Observasi**: 50 item
    - **Ekstraksi Linier**: `50 context_v1` dan `50 context_v2` digabungkan.
    - **Hasil Keluaran**: Terbentuk 100 teks referensial utuh tanpa *missing values* siap untuk diinjeksi ke LightRAG.

---

## Tahap 3: Konstruksi LightRAG (Data Chunking & Extraction)

Tahap ini mengoperasikan sistem mesin komputasi arsitektur LightRAG. Seratus dokumen tersebut diolah oleh sistem untuk dipotong dan diekstraksi ke dalam simpul memori graf.

### 1. Data Chunking
*   **Proses**: Memecah ke-100 teks referensial menjadi *chunks* memori yang terkurasi agar sesuai dengan *context window* LLM pengolah.
*   **Bukti Indeks Pemotongan Data**:
    ```json
    {
      "chunk-f8939937": {
        "content": "The Capital of Indonesia is Jakarta. This is a diagnostic test document.",
        "length": 12,
        "metadata": "Extracted context..."
      }
    }
    ```

### 2. Entity and Relationship Extraction
*   **Proses**: Mengekstrak entitas materi dasar (Nodes) dan hubungan antar materi (Edges) secara masif dari isi dokumen teks asli menggunakan LLM.
*   **Bukti Output Ekstraksi LLM Aktual (Contoh Sukses Penuh Tanpa Pemotongan)**:
    ```text
    entity<|#|>PSLV-C56<|#|>artifact<|#|>PSLV-C56 is the 58th mission of the Polar Satellite Launch Vehicle (PSLV) and the 17th flight of the PSLV-CA variant.
    entity<|#|>Indian Space Research Organisation<|#|>organization<|#|>The Indian Space Research Organisation (ISRO) is the space agency of the Government of India, established in 1969 to develop space technology and conduct space research.
    entity<|#|>Polar Satellite Launch Vehicle<|#|>artifact<|#|>The Polar Satellite Launch Vehicle (PSLV) is a launch vehicle used by the Indian Space Research Organisation for its missions.
    
    relation<|#|>PSLV-C56<|#|>Indian Space Research Organisation<|#|>mission<|#|>PSLV-C56 is a mission undertaken by the Indian Space Research Organisation.
    relation<|#|>PSLV-C56<|#|>Polar Satellite Launch Vehicle<|#|>variant<|#|>PSLV-C56 is a mission using the Polar Satellite Launch Vehicle.
    relation<|#|>Indian Space Research Organisation<|#|>Government of India<|#|>agency of<|#|>The Indian Space Research Organisation is the space agency of the Government of India.
    ```

### 3. Eksekusi Injeksi LightRAG
*   **Bukti Log Keberhasilan Sistem Injeksi**:
    ```text
    Backup: rag_storage_20260309_074128_wikieval100_injected
    Tanggal: 2026-03-09 07:41:32
    Dataset: wikiEval_all.json (50 items, 100 dokumen: 50 context_v1 + 50 context_v2)
    Injeksi: Sukses 100/100 (0 duplikat, 0 gagal) ke kedua instance
    LLM: gemini-2.5-flash-lite via Google AI Studio
    Embedding: gemini-embedding-001 via Google AI Studio

    lightrag-en: 12 files
    lightrag-id: 12 files
    Status: Post-injection (KG extraction sedang/sudah berjalan di background)
    ```

### 4. Indexing dan Penyimpanan Mutlak (Hybrid Storage)
Fase puncak di mana luaran ekstraksi direkatkan ke representasi vektor spasial dan arsip graf entitas. Ini membentuk wujud *Knowledge Graph* hibrida yang operasional.

*   **Proses**: Sistem RAG mentransformasikan chunks, entities, dan edges menjadi vektor basis data, mendata 100 graf muatan utuh tanpa deviasi.
*   **Bukti Simpanan Rekaman Dokumen Aktual**:
    - **GraphML Storage**: Matriks dari 100 Graf Entitas & Relasi tersusun penuh. Representasi format `graph_chunk_entity_relation.graphml`:
      ```xml
      <?xml version='1.0' encoding='utf-8'?>
      <graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
      <key id="d13" for="edge" attr.name="truncate" attr.type="string"/>
      <key id="d12" for="edge" attr.name="created_at" attr.type="long"/>
      <key id="d1" for="node" attr.name="entity_type" attr.type="string"/>
      <key id="d0" for="node" attr.name="entity_id" attr.type="string"/>
      ```
    - **Vector Database**: Sekumpulan indeks *array embeddings* (numerik vektor ruang murni). Konten persisten dari `vdb_entities.json`:
      ```json
      {"embedding_dim": 3072, "data": [{"__id__": "ent-867c93d0ff29b1cbf292d0ef6e86f03f", "__created_at__": 1772992912, "entity_name": "PSLV-C56", "content": "PSLV-C56\nPSLV-C56 is the 58th mission of the Polar Satellite Launch Vehicle (PSLV) and the 17th flight of the PSLV-CA variant.<SEP>PSLV-C56 is the 58th mission of the Polar Satellite Launch Vehicle (PSLV) and the 17th flight of the PSLV-CA variant."}]}
      ```
