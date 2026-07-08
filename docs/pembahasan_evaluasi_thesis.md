# Daftar Pembahasan Evaluasi untuk Skripsi

Dokumen ini berisi daftar poin pembahasan yang dapat diangkat dari dashboard Streamlit untuk bagian evaluasi faithfulness dan evaluasi koherensi naratif (Bab 4). Susunan ini telah diatur secara metodologis menggunakan pendekatan deduktif (dari tingkat makro populasi ke tingkat mikro kasus kualitatif) dan dibebaskan dari redundansi penulisan serta parameter teknis yang tidak relevan.

---

## 4.2 Evaluasi Faithfulness

### 4.2.1 Statistik Skor Faithfulness (Tingkat Trace)

- **Distribusi skor RAGAS Standard Faithfulness**: Analisis histogram dan KDE. Apakah distribusi terkonsentrasi di nilai tinggi (ceiling effect)? Apa implikasinya terhadap kemampuan diskriminatif metrik?
- **Distribusi skor FABLES Faithfulness**: Bandingkan dengan distribusi RAGAS. FABLES cenderung lebih tinggi karena mengecualikan CANT_VERIFY dari pembilang dan penyebut.
- **Rata-rata Faithfulness (RAGAS + FABLES) / 2**: Apakah rata-rata gabungan memberikan gambaran yang lebih representatif?
- **Statistik deskriptif**: Mean, Median, Std, Min, Max, Q25, Q75. Bahas skewness distribusi dan ada atau tidaknya pencilan (outlier).
- **Sampling markers (min/mean/max)**: Pembuktian kuantitatif apakah subset 10 cerita sampling skripsi representatif terhadap distribusi populasi keseluruhan (5 cerita EN dan 5 cerita ID).

### 4.2.2 Agregasi Jumlah Klaim per Label

- **Komposisi 4 label (FAITHFUL, UNFAITHFUL, PARTIAL_SUPPORT, CANT_VERIFY)**: Proporsi masing-masing label dari total klaim. Label mana yang mendominasi?
- **Perbandingan per bahasa (EN vs ID)**: Apakah ada perbedaan signifikan dalam proporsi label antara cerita berbahasa Indonesia dan Inggris?
- **Distribusi jumlah klaim per cerita**: Apakah jumlah klaim yang diekstrak bervariasi signifikan antar cerita? Apa faktor yang mempengaruhi (panjang cerita, kompleksitas topik)?

### 4.2.3 Performa Klasifikasi Klaim (Confusion Matrix 2x2)

- **Macro F1-Score**: Nilai keseluruhan performa model LLM-as-a-Judge dalam mengklasifikasikan klaim sebagai Faithful vs Unfaithful. Bandingkan antara standar FABLES dan RAGAS.
- **Precision kelas Faithful dan Recall kelas Unfaithful**: Seberapa akurat model ketika memprediksi suatu klaim sebagai Faithful (menganalisis kebocoran False Positive)? Bagaimana kemampuan model menangkap klaim yang benar-benar tidak setia (menganalisis dampak Recall rendah)?
- **Penanganan label CANT_VERIFY dan PARTIAL_SUPPORT (Implikasi Metodologis)**: Perbedaan FABLES (Kim et al., 2024) yang mengecualikan kedua label ini dari matriks 2x2 vs RAGAS Standard yang memasukkan semua klaim secara strict. Bahas dampaknya terhadap peningkatan nilai False Positive (FP), Precision, dan perbedaan Delta FP antara kedua standar.

### 4.2.4 Penelusuran Klaim dan Highlight HTML (Analisis Kualitatif)

- **Verifikasi manual klaim vs konteks sumber**: Audit 10 cerita sampling berdasarkan validasi ahli materi. Apakah highlight (Ref:Klaim N) menunjuk ke kalimat sumber riset yang tepat dan informatif?
- **Kasus Planner-only (Story 8 - Menara Jam Chimnabai)**: Beberapa klaim hanya memiliki bukti di dalam Rencana Cerita (Planner Output), bukan di sumber riset asli. Bahas keterbatasan retrieval dalam kasus informasi yang sangat spesifik.
- **Kasus cerita skor rendah (Story 9 - Gaucho Americano, Story 10 - Roanoke Railroad)**: Analisis kualitatif terhadap klaim UNFAITHFUL. Apakah ketidaksetiaan disebabkan oleh halusinasi LLM atau kegagalan retrieval?

### 4.2.5 Perbandingan Baseline vs Agentic AI (Faithfulness)

- **Distribusi skor overlaid (Baseline vs Agentic AI)**: Visualisasi histogram dan boxplot beserta ringkasan statistik deskriptif (Delta Mean) untuk metrik FABLES dan RAGAS. Apakah sistem Agentic AI menunjukkan distribusi skor yang lebih tinggi atau lebih terkonsentrasi?
- **Uji signifikansi Mann-Whitney U (one-sided)**: Apakah peningkatan skor Agentic AI vs Baseline signifikan secara statistik (p < 0.05)?
- **Cohen's d (effect size)**: Besar efek peningkatan. Apakah efeknya kecil (d < 0.2), sedang (0.2-0.8), atau besar (d > 0.8)?
- **Analisis klaim dan label FABLES (Baseline vs Agentic AI)**: Perbandingan jumlah klaim total per cerita serta perbandingan proporsi label FAITHFUL, UNFAITHFUL, PARTIAL_SUPPORT, dan CANT_VERIFY antara kedua sistem.

---

## 4.3 Evaluasi Koherensi Naratif

### 4.3.1 G-Eval: Kualitas Linguistik (DeepEval)

- **5 sub-kriteria G-Eval**: Fluency (tata bahasa, sintaks), Consistency (suara naratif), Clarity (kejelasan bahasa), Conciseness (tidak bertele-tele), Repetitiveness (tidak berulang). Bahas relevansi masing-masing dimensi untuk cerita edukasi.
- **Skor rata-rata G-Eval (1-5)**: Mean, Std, Min, Max untuk seluruh 100 trace. Apakah ada ceiling effect?
- **Distribusi per dimensi (histogram + boxplot)**: Dimensi mana yang paling bervariasi? Dimensi mana yang cenderung mendapat skor tinggi secara konsisten?
- **G-Eval Normalized (0-1)**: Konversi skor 1-5 ke skala 0-1. Formula: `normalized = (raw - 1) / 4`.

### 4.3.2 Ground Truth: Validasi Ahli Bahasa

- **Instrumen penilaian 13 butir**: Pemetaan 13 butir penilaian oleh ahli bahasa ke 5 dimensi G-Eval (Fluency: butir 1-5, Consistency: butir 6-7, Clarity: butir 8-11, Conciseness: butir 12, Repetitiveness: butir 13).
- **Distribusi bobot per dimensi**: Fluency memiliki 5 butir, Clarity memiliki 4 butir, sedangkan Conciseness dan Repetitiveness masing-masing hanya 1 butir. Bahas implikasi ketidakseimbangan ini terhadap sensitivitas pengukuran.
- **Tabel GT vs Pred (diwarnai)**: Identifikasi pola per bahasa pada 10 cerita sampel. Di dimensi mana model auto-grade cenderung menyimpang dari penilaian ahli bahasa?
- **Ringkasan rata-rata per cerita (13 butir)**: Cerita mana yang mendapat skor tertinggi atau terendah menurut ahli bahasa? Apakah ranking ahli bahasa konsisten dengan ranking auto-grade?
- **Perbandingan antar bahasa (ID vs EN)**: Apakah kualitas koherensi cerita berbahasa Indonesia berbeda signifikan dengan cerita berbahasa Inggris menurut validasi ahli bahasa?

### 4.3.3 Performa Klasifikasi (Expert Judgement vs Auto-Grade)

- **Evaluasi Klasifikasi Multi-kelas (G-Eval vs Ahli Bahasa)**: Laporan klasifikasi komprehensif yang memadukan metrik akurasi pencocokan persis (Exact Match Accuracy), matriks konfusi multi-kelas (1-5) untuk mendeteksi pola bias penilaian (overestimation/underestimation), serta analisis Precision, Recall, F1-Score (baik Macro, Weighted, maupun per kelas label 1-5).
- **Total label dievaluasi**: 5 dimensi x jumlah cerita sampel per bahasa. Bahas ukuran sampel dan representativitasnya untuk pengujian performa auto-grader.

### 4.3.4 Perbandingan Baseline vs Agentic AI (Koherensi)

- **Distribusi skor G-Eval per dimensi (overlaid)**: Visualisasi histogram dan boxplot beserta statistik deskriptif (Delta Mean) untuk setiap dimensi koherensi naratif (Fluency, Consistency, Clarity, Conciseness, Repetitiveness). Apakah Agentic AI konsisten lebih baik di semua dimensi?
- **Uji signifikansi Mann-Whitney U dan Cohen's d per dimensi**: Apakah peningkatan skor signifikan secara statistik (p < 0.05) dan seberapa besar efek peningkatan (effect size) untuk masing-masing dimensi?

---

## 4.4 Temuan Lintas-Evaluasi (Faithfulness x Koherensi)

- **Korelasi faithfulness dan koherensi**: Apakah cerita dengan skor faithfulness tinggi juga cenderung memiliki skor koherensi tinggi? Atau apakah kedua aspek ini independen?
- **Trade-off antara faithfulness dan kreativitas naratif**: Cerita yang sangat setia terhadap konteks mungkin terasa kaku secara naratif. Sebaliknya, cerita yang koheren dan mengalir baik mungkin mengambil kebebasan kreatif yang mengurangi faithfulness.
- **Dampak bahasa terhadap kedua metrik**: Apakah pola performa berbeda antara cerita EN dan ID secara konsisten di kedua evaluasi?
- **Peran loop revisi terhadap peningkatan kedua metrik**: LLM Coherence Evaluator aktif dalam loop revisi; apakah ini juga secara tidak langsung meningkatkan faithfulness (melalui perbaikan naratif yang lebih terstruktur)?

---

## Catatan Teknis

- Seluruh data bersumber dari export Langfuse (CSV Traces dan JSONL Observations) di folder `Eval_Data/`.
- Dashboard Streamlit: `Streamlit/tabs/faithfulness.py` and `Streamlit/tabs/coherence.py`.
- Ground truth faithfulness: penyesuaian manual pada visualisasi HTML di `generate_faithfulness_images_10.py`.
- Ground truth koherensi: tabel validasi ahli bahasa 13 butir x 5 cerita per bahasa (hardcoded di `coherence.py`).
