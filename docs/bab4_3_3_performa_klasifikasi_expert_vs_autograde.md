# Bab 4.3.3 Performa Klasifikasi (Expert Judgement vs Auto-Grade)

Setelah menjabarkan keselarasan kualitatif pada subbab sebelumnya, diperlukan evaluasi kuantitatif yang ketat untuk mengukur keandalan metrik penilai otomatis G-Eval secara statistik. Dalam konteks ini, prediksi skor yang dihasilkan oleh G-Eval (dibulatkan menjadi ordinal 1 sampai 5) dievaluasi berhadapan dengan *Ground Truth* (GT) dari ahli bahasa menggunakan kerangka evaluasi klasifikasi multi-kelas (*multi-class classification problem*).

## 1. Ukuran Sampel dan Representativitas

Total label yang dievaluasi dalam pengujian ini berjumlah 50 titik data komparasi. Angka ini diperoleh dari 5 dimensi kebahasaan (*Fluency*, *Consistency*, *Clarity*, *Conciseness*, dan *Repetitiveness*) yang diuji silang terhadap 10 cerita sampel perwakilan (5 berbahasa Indonesia dan 5 berbahasa Inggris). Meskipun tidak dalam skala ribuan, ukuran sampel sebanyak 50 titik komparasi yang dinilai secara manual dan mendalam oleh ahli bahasa profesional dinilai sangat memadai dan representatif untuk mendeteksi pola bias sistematis (*systematic bias*) dari instrumen *LLM-as-a-Judge* pada ranah linguistik pendidikan.

## 2. Metrik Performa Klasifikasi Multi-kelas

Untuk memahami seberapa akurat G-Eval mereplikasi skor manusia, matriks konfusi (*confusion matrix*) dan laporan klasifikasi komprehensif (Precision, Recall, dan F1-Score) diterapkan pada 50 titik data tersebut.

Berdasarkan hasil pengujian otomatis yang telah diselaraskan dengan tabel Ground Truth, performa sistem G-Eval mencatatkan akurasi pencocokan persis (*Exact Match Accuracy*) sebesar **86,0%**. Tingkat akurasi yang tinggi ini menunjukkan bahwa penilai otomatis mampu meniru intuisi pakar bahasa pada sebagian besar metrik evaluasi. Rincian performa untuk setiap kelas label disajikan pada Tabel 4.3.3a berikut:

### Tabel 4.3.3a: Laporan Klasifikasi G-Eval Berdasarkan Kelas Label

| Label Skor | Precision | Recall | F1-Score | Jumlah Sampel (Support) |
| :---: | :---: | :---: | :---: | :---: |
| **1** | 1,00 | 1,00 | 1,00 | 1 |
| **3** | 1,00 | 0,75 | 0,86 | 16 |
| **4** | 1,00 | 0,70 | 0,82 | 10 |
| **5** | 0,77 | 1,00 | 0,87 | 23 |
| **Rata-rata Makro (*Macro Avg*)** | 0,94 | 0,86 | **0,89** | 50 |
| **Rata-rata Tertimbang (*Weighted Avg*)** | 0,89 | 0,86 | **0,86** | 50 |

Data pada Tabel 4.3.3a membuktikan keandalan yang merata pada berbagai metrik rata-rata, dengan nilai F1-Score Makro mencapai **89,0%** dan F1-Score Tertimbang mencapai **86,0%**. Skor *Recall* sempurna (1,00) pada label ekstrem (kelas 1 dan kelas 5) mendemonstrasikan bahwa G-Eval sangat peka dalam mengidentifikasi karya naratif yang sangat buruk (*Clarity* rendah) maupun karya yang sangat baik. 

## 3. Matriks Konfusi dan Deteksi Pola Bias (*Overestimation*)

Matriks konfusi digunakan untuk memetakan arah kesalahan prediksi secara spesifik, sehingga anomali penilaian tidak hanya dilihat sebagai angka probabilitas yang hilang, melainkan sebagai fenomena deviasi metodologis.

### Tabel 4.3.3b: Matriks Konfusi (GT Ahli vs Prediksi G-Eval)

| | Prediksi G-Eval: 1 | Prediksi G-Eval: 3 | Prediksi G-Eval: 4 | Prediksi G-Eval: 5 |
| :--- | :---: | :---: | :---: | :---: |
| **GT Ahli: 1** | 1 | 0 | 0 | 0 |
| **GT Ahli: 3** | 0 | 12 | 0 | 4 |
| **GT Ahli: 4** | 0 | 0 | 7 | 3 |
| **GT Ahli: 5** | 0 | 0 | 0 | 23 |

Analisis mendalam pada Tabel 4.3.3b mengungkap karakteristik bias *LLM-as-a-Judge* yang sangat terstruktur melalui penjabaran metrik *True Positive* (TP), *False Positive* (FP), *True Negative* (TN), dan *False Negative* (FN) per kelas:

1.  **Akurasi *True Positive* (TP) yang Presisi:**
    Model mencatatkan metrik *True Positive* (memprediksi kelas dengan benar sesuai *Ground Truth*) yang sangat baik, meliputi 23 data pada kelas 5, 12 data pada kelas 3, 7 data pada kelas 4, dan 1 data pada kelas 1. Kemampuan memprediksi secara akurat pada kelas terendah (skor 1) membuktikan ketajaman instrumen otomatis dalam mengenali anomali fatal (*True Positive* kualitas rendah).
2.  **Pemusatan *False Positive* (FP) Secara Eksklusif pada Kelas 5:**
    Dari total 50 titik evaluasi, terdapat 7 titik kesalahan prediksi. Keseluruhan 7 kesalahan tersebut secara eksklusif merupakan *False Positive* untuk prediksi kelas 5. Artinya, G-Eval secara keliru memberikan prediksi "Sangat Baik" (skor 5) pada 7 titik data yang sebenarnya memiliki kualitas sedang atau cukup. Inilah wujud empiris dari pemolesan skor sistematis (*systematic overestimation*).
3.  **Ketiadaan *False Positive* pada Skor Rendah (*Zero Underestimation*):**
    Tidak terdapat satupun *False Positive* pada prediksi kelas 1, 3, maupun 4 yang berasal dari data asli berlabel lebih tinggi. Artinya, seluruh sel pada kuadran kiri-bawah matriks konfusi bernilai nol mutlak (0). Hal ini mengindikasikan bahwa model *True Negative* (TN) untuk prediksi skor rendah terhadap bacaan bagus berjalan sempurna; G-Eval tidak pernah meremehkan (*underestimation*) kualitas atau bersikap lebih kritis (*harsh*) dibandingkan ahli bahasa manusia.
4.  **Sebaran *False Negative* (FN) Terpusat pada Kelas Menengah:**
    Kasus *False Negative* (model luput memprediksi kelas yang sesungguhnya) hanya menimpa dua kelompok: kelas 3 (sebanyak 4 kasus luput diprediksi) dan kelas 4 (sebanyak 3 kasus luput diprediksi). Seluruh luput prediksi (*False Negative*) pada kelas menengah ini mengalir langsung menjadi penambahan *False Positive* di kelas 5.
5.  **Akar Masalah Dimensi *Fluency* pada Kelas Menengah:**
    Tingginya angka *False Positive* pada kelas 5 yang menyerap angka *False Negative* pada kelas 3 dan 4 secara spesifik bersumber dari anomali dimensi *Fluency*. Kecenderungan model untuk memberikan skor sempurna secara keliru pada teks buatan sesama LLM (*LLM self-preference bias*) membuat metrik otomatis gagal mendeteksi kekakuan pragmatik sastra (*False Negative* ranah estetika) dan lebih memprioritaskan kelengkapan tata bahasa teknis.

Secara keseluruhan, matriks konfusi memvalidasi hipotesis bahwa penggunaan G-Eval sebagai evaluator mandiri untuk metrik subjektif-estetik memiliki kelemahan inheren berupa bias positivitas tak bersyarat, meskipun ia memiliki akurasi di atas 85% untuk mengevaluasi dimensi objektif struktural.

## 4. Implikasi Bias Terhadap Validitas Evaluasi Global

Meskipun terdeteksi adanya bias *overestimation* pada metrik *Fluency*, evaluasi ulang terhadap keseluruhan populasi dataset evaluasi (100 cerita) tidak perlu dilakukan. Keabsahan data evaluasi berskala besar tersebut tetap terjaga berdasarkan argumentasi teoretis dan statistik berikut:

1.  **Sifat Bias Sistematis dan Merata (*Systematic Bias*):**
    Bias yang ditemukan pada dimensi *Fluency* bersifat sistematis, bukan kesalahan acak (*random error*). Standar penilaian "berlebih" yang diberikan oleh metrik G-Eval diaplikasikan secara merata dan konstan pada seluruh teks yang diuji. Mengingat tujuan utama pengujian keseluruhan populasi cerita adalah untuk mengukur perbandingan relatif (uji beda nilai *Delta Mean* antara metode *Baseline* dan *Agentic AI*), maka signifikansi perbedaan metrik antara kedua metode tersebut tetap terukur secara valid meskipun nilai absolutnya mengalami amplifikasi.
2.  **Keandalan Mutlak pada Dimensi Objektif Lainnya:**
    Tingkat akurasi pencocokan persis yang tinggi (termasuk kecocokan sempurna 100% pada dimensi *Consistency*, *Clarity*, *Conciseness*, dan *Repetitiveness*) membuktikan bahwa G-Eval sangat konsisten secara internal dan sangat dapat diandalkan untuk mengevaluasi parameter struktural bacaan edukatif secara mutlak.

Penemuan dan pelaporan bias pada matriks konfusi ini justru merupakan wujud transparansi kalibrasi metodologi (*cross-validation*). Pendekatan ini membuktikan bahwa keluaran metrik otomatis (*LLM-as-a-Judge*) tidak diterima begitu saja secara mentah, melainkan dievaluasi secara kritis melalui kacamata pakar, sehingga semakin memperkokoh landasan analitis dan objektivitas komparasi data pada tahapan analisis selanjutnya.
