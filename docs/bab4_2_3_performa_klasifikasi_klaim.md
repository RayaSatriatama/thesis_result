# 4.2.3 Performa Klasifikasi Klaim (Confusion Matrix 2x2)

Subbab ini menyajikan hasil evaluasi performa model LLM-as-a-Judge (GPT-4o) dalam melakukan klasifikasi klaim cerita (Faithful vs Unfaithful). Evaluasi dilakukan dengan membandingkan prediksi otomatis dari model pengevaluasi terhadap hasil validasi ahli materi (ground truth) yang telah disesuaikan melalui validasi ulang pada sepuluh cerita sampel skripsi (lima cerita berbahasa Inggris dan lima cerita berbahasa Indonesia) yang terbukti representatif pada subbab 4.2.1. Performa klasifikasi dianalisis menggunakan dua standar metodologi evaluasi: standar FABLES Framework dan standar RAGAS Standard.

---

## 1. Hasil Pengukuran dan Confusion Matrix

Evaluasi performa didasarkan pada total 117 klaim yang diekstrak dari sepuluh cerita sampel. Perbedaan utama antara FABLES dan RAGAS terletak pada penanganan label klaim tingkat menengah, yaitu PARTIAL_SUPPORT dan CANT_VERIFY.

### A. Standar FABLES Framework
Berdasarkan standar FABLES (Kim et al., 2024), matriks konfusi 2x2 hanya mengevaluasi klaim yang diprediksi sebagai FAITHFUL atau UNFAITHFUL secara tegas. Klaim dengan label CANT_VERIFY dan PARTIAL_SUPPORT dikeluarkan dari perhitungan matriks konfusi 2x2, kecuali kasus khusus yang ditandai secara manual oleh ahli materi sebagai ground truth faithful tetapi diprediksi sebagai PARTIAL_SUPPORT (dianggap sebagai False Negative). 

Berdasarkan data observasi riil, terdapat 1 klaim berlabel PARTIAL_SUPPORT yang dieksklusi pada dataset keseluruhan (berasal dari cerita berbahasa Inggris). Dengan demikian, total klaim yang dievaluasi dalam matriks konfusi FABLES adalah 116 klaim.

Berikut adalah tabel matriks konfusi 2x2 untuk standar FABLES:

| Realitas \ Prediksi | Faithful (Positif) | Unfaithful (Negatif) | Total |
| :--- | :---: | :---: | :---: |
| **Faithful** (Positif) | 107 (True Positive) | 1 (False Negative) | 108 |
| **Unfaithful** (Negatif) | 1 (False Positive) | 7 (True Negative) | 8 |
| **Total** | 108 | 8 | 116 |

### B. Standar RAGAS Standard
Standar RAGAS menggunakan pendekatan strict di mana seluruh klaim dimasukkan ke dalam matriks konfusi 2x2. Sisi prediksi positif hanya diisi oleh klaim berlabel FAITHFUL. Sebaliknya, klaim yang berlabel UNFAITHFUL, PARTIAL_SUPPORT, dan CANT_VERIFY digabungkan ke dalam sisi prediksi negatif (tidak setia sepenuhnya). 

Dengan pendekatan ini, total klaim yang dievaluasi adalah 117 klaim keseluruhan tanpa ada yang dieksklusi. Berikut adalah tabel matriks konfusi 2x2 untuk standar RAGAS:

| Realitas \ Prediksi | Faithful (Positif) | Unfaithful (Negatif) | Total |
| :--- | :---: | :---: | :---: |
| **Faithful** (Positif) | 107 (True Positive) | 1 (False Negative) | 108 |
| **Unfaithful** (Negatif) | 1 (False Positive) | 8 (True Negative) | 9 |
| **Total** | 108 | 9 | 117 |

---

## 2. Classification Report dan Metrik Evaluasi

Berdasarkan matriks konfusi di atas, metrik performa klasifikasi untuk masing-masing standar dihitung secara rinci (keseluruhan, bahasa Inggris, dan bahasa Indonesia).

### A. Metrik Performa Keseluruhan (Gabungan EN dan ID)

Tabel berikut menunjukkan perbandingan classification report antara standar FABLES dan RAGAS:

| Metrik | FABLES Framework | RAGAS Standard | Selisih (Delta) |
| :--- | :---: | :---: | :---: |
| **Precision (Faithful)** | 99.07% | 99.07% | 0.00% |
| **Recall (Faithful)** | 99.07% | 99.07% | 0.00% |
| **F1-Score (Faithful)** | 99.07% | 99.07% | 0.00% |
| **Precision (Unfaithful)** | 87.50% | 88.89% | +1.39% |
| **Recall (Unfaithful)** | 87.50% | 88.89% | +1.39% |
| **F1-Score (Unfaithful)** | 87.50% | 88.89% | +1.39% |
| **Macro F1-Score** | 93.29% | 93.98% | +0.69% |
| **Total Klaim Dievaluasi** | 116 | 117 | +1 klaim |

### B. Metrik Performa Berdasarkan Bahasa Inggris (EN)
Berdasarkan sub-populasi lima cerita berbahasa Inggris (total 64 klaim, di mana 1 klaim PARTIAL_SUPPORT dieksklusi pada standar FABLES):

- **FABLES Framework (EN)**:
  - TP: 59, FP: 0, TN: 3, FN: 1
  - Precision (Faithful): 100.00%
  - Recall (Faithful): 98.33%
  - F1-Score (Faithful): 99.16%
  - Precision (Unfaithful): 75.00%
  - Recall (Unfaithful): 100.00%
  - F1-Score (Unfaithful): 85.71%
  - **Macro F1-Score (EN)**: 92.44%
- **RAGAS Standard (EN)**:
  - TP: 59, FP: 0, TN: 4, FN: 1
  - Precision (Faithful): 100.00%
  - Recall (Faithful): 98.33%
  - F1-Score (Faithful): 99.16%
  - Precision (Unfaithful): 80.00%
  - Recall (Unfaithful): 100.00%
  - F1-Score (Unfaithful): 88.89%
  - **Macro F1-Score (EN)**: 94.02%

### C. Metrik Performa Berdasarkan Bahasa Indonesia (ID)
Berdasarkan sub-populasi lima cerita berbahasa Indonesia (total 53 klaim, tanpa eksklusi klaim pada kedua standar):

- **FABLES Framework & RAGAS Standard (ID)**:
  - TP: 48, FP: 1, TN: 4, FN: 0
  - Precision (Faithful): 97.96%
  - Recall (Faithful): 100.00%
  - F1-Score (Faithful): 98.97%
  - Precision (Unfaithful): 100.00%
  - Recall (Unfaithful): 80.00%
  - F1-Score (Unfaithful): 88.89%
  - **Macro F1-Score (ID)**: 93.93%

*(Catatan: Karena tidak ada klaim berlabel CANT_VERIFY atau PARTIAL_SUPPORT pada subset Bahasa Indonesia, performa FABLES dan RAGAS menghasilkan nilai yang identik).*

---

## 3. Analisis dan Interpretasi Metrik

### A. Macro F1-Score
Nilai Macro F1-Score yang tinggi (93.29% pada FABLES dan 93.98% pada RAGAS) membuktikan tingkat keselarasan yang sangat kuat antara evaluasi otomatis LLM-as-a-Judge dan validasi ahli materi. Perbedaan sebesar +0.69% pada standar RAGAS didorong oleh klasifikasi 1 klaim PARTIAL_SUPPORT yang dimasukkan sebagai True Negative (TN) pada standar RAGAS, meningkatkan performa pendeteksian klaim tidak setia secara keseluruhan.

### B. Precision Kelas Faithful
Precision kelas Faithful mencapai 99.07% untuk kedua standar. Nilai ini sangat tinggi dan menunjukkan tingkat keyakinan yang luar biasa ketika model menandai sebuah klaim sebagai faithful. Terjadinya False Positive (FP) sangat minim, di mana hanya ada 1 kasus klaim tidak setia yang lolos sebagai faithful. Nilai Precision tinggi ini sangat krusial bagi sistem edukasi agar cerita yang disajikan kepada siswa bebas dari kesalahan informasi (halusinasi).

### C. Recall Kelas Unfaithful
Recall kelas Unfaithful menggambarkan kemampuan model menangkap pelanggaran kesetiaan konteks secara tepat. Pada FABLES, diperoleh nilai Recall sebesar 87.50% (7 dari 8 klaim unfaithful terdeteksi), sementara pada RAGAS didapatkan nilai 88.89% (8 dari 9 klaim terdeteksi). Nilai Recall yang tinggi ini menandakan model sangat sensitif dalam mendeteksi ketidaksetiaan fakta dan meminimalkan kebocoran kesalahan informasi yang tidak terdeteksi.

---

## 4. Analisis Kasus Spesifik (False Positive dan False Negative)

### A. Analisis Kualitatif Kasus False Positive (FP)
Hanya terdapat 1 kasus False Positive yang teridentifikasi dalam evaluasi sepuluh cerita sampel, yaitu pada **Story 9 (Kategori Skor Rendah berbahasa Indonesia)**, klaim 1.
- **Klaim**: Menyatakan adanya hubungan geografis spesifik dengan arkeologi Skotlandia.
- **Masalah**: Model pengevaluasi melabeli klaim tersebut sebagai FAITHFUL. Namun, berdasarkan validasi ahli materi, bukti retrieval yang diberikan oleh LightRAG murni membahas arkeologi Indonesia dan tidak mendukung fakta tentang Skotlandia. Kasus ini dikategorikan sebagai False Positive karena model pengevaluasi mengalami halusinasi atau gagal membandingkan klaim naratif cerita secara ketat terhadap fakta retrieval eksternal. Kasus ini menekankan pentingnya pembatasan konteks retrieval eksternal dalam alur kerja agen pengkritik.

### B. Analisis Kualitatif Kasus False Negative (FN)
Terdapat 1 kasus False Negative yang teridentifikasi dalam evaluasi sepuluh cerita sampel, yaitu pada **Story 5 (Kategori Skor Rendah berbahasa Inggris)**, klaim 8 (Gempa Hormozgan).
- **Klaim**: Membahas mengenai detail gempa Hormozgan.
- **Masalah**: Model pengevaluasi melabeli klaim tersebut sebagai PARTIAL_SUPPORT dalam ekspor mentah karena kalimat dalam cerita tidak menggunakan kutipan harfiah melainkan parafrasa. Namun, validasi ahli materi membuktikan bahwa makna klaim tersebut didukung penuh secara faktual oleh kalimat retrieval. Berdasarkan standar FABLES, ketidaksesuaian ini diklasifikasikan sebagai False Negative karena model gagal mengenali parafrasa yang valid dan memilih opsi label yang lebih lemah secara metodologis.

---

## 5. Implikasi Metodologis Penanganan Label CANT_VERIFY dan PARTIAL_SUPPORT

Perbedaan penanganan label tingkat menengah memberikan dampak langsung pada metrik Precision dan jumlah False Positive:
1. **Pengecualian FABLES**: Dengan mengecualikan CANT_VERIFY dan PARTIAL_SUPPORT, FABLES berfokus murni pada klaim biner yang jelas (setia vs tidak setia). Hal ini berguna untuk menghindari bias nilai akibat ketidakpastian model dalam mencocokkan informasi yang tidak lengkap secara tekstual.
2. **Keterikatan RAGAS**: RAGAS secara ketat menganggap segala bentuk ketidaklengkapan dukungan (PARTIAL_SUPPORT) atau ketiadaan bukti (CANT_VERIFY) sebagai kegagalan kesetiaan (kelas negatif). Pendekatan ini meningkatkan nilai True Negative (TN) ketika model berhasil menandai klaim tersebut sebagai bukan FAITHFUL, sehingga meningkatkan nilai Macro F1-Score sebesar 0.69%. Pendekatan ini lebih cocok diterapkan pada sistem produksi yang menuntut tingkat kebenaran mutlak (zero-tolerance terhadap informasi tanpa bukti).

---

## 6. Bukti Visual dari Dashboard Streamlit

Berikut adalah bukti tangkapan layar visual dari modul evaluasi Faithfulness pada Streamlit yang menunjukkan matriks konfusi dan laporan klasifikasi riil untuk kedua standar evaluasi:

### A. Tampilan Modul Evaluasi FABLES Framework
Tangkapan layar ini menampilkan visualisasi Confusion Matrix 2x2 dan Classification Report di bawah standar FABLES dengan total 116 klaim yang dievaluasi.

![Confusion Matrix dan Classification Report FABLES Framework](../assets/evaluation/4.2.1_fables_confusion_matrix.png)

### B. Tampilan Modul Evaluasi RAGAS Standard
Tangkapan layar ini menampilkan visualisasi Confusion Matrix 2x2 dan Classification Report di bawah standar RAGAS dengan total 117 klaim yang dievaluasi secara ketat.

![Confusion Matrix dan Classification Report RAGAS Standard](../assets/evaluation/4.2.1_ragas_confusion_matrix.png)
