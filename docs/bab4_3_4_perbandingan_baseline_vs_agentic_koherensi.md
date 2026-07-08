# Bab 4.3.4 Perbandingan Baseline vs *Agentic* AI (Koherensi)

Setelah memastikan keandalan instrumen evaluasi otomatis melalui validasi pakar pada subbab sebelumnya, tahap analisis selanjutnya adalah melakukan uji komparatif skala penuh antara pendekatan *Baseline* (pembuatan cerita tanpa agen) dan *Agentic* AI (menggunakan alur kerja berbasis agen (*agentic workflow*) dan *LLM Coherence Evaluator*). Pengujian ini menggunakan skor G-Eval Normalized secara global serta membedah 5 dimensi koherensi secara spesifik (*Fluency, Consistency, Clarity, Conciseness, Repetitiveness*).

Seluruh pengujian statistik pada subbab ini menggunakan uji non-parametrik **Mann-Whitney U** mengingat distribusi skor yang dihasilkan oleh *LLM-as-a-Judge* tidak selalu berdistribusi normal (sebagian besar metrik mengalami *ceiling effect* mendekati skor maksimal 5). Besaran efek dari peningkatan yang terjadi diukur menggunakan **Cohen's d** untuk memberikan gambaran kuantitatif mengenai signifikansi praktis dari metode *Agentic*.

## 1. Perbandingan Global (G-Eval Coherence Normalized)

Secara makro, metrik koherensi yang dinormalisasi (skala 0-1) menunjukkan bahwa sistem *Agentic* AI memiliki keunggulan yang sangat dominan.
*   **Rata-rata Baseline**: 0,780
*   **Rata-rata *Agentic* AI**: 0,893
*   **Delta (Peningkatan)**: +0,113
*   **Nilai p (Mann-Whitney U)**: p < 0,001 (1,99e-11)
*   **Cohen's d**: 1,004 (Efek Sangat Besar / *Large Effect*)

Peningkatan sebesar lebih dari 11% dengan ukuran efek di atas 1,0 membuktikan bahwa orkestrasi multi-agen (khususnya iterasi revisi oleh agen *Evaluator*) sukses besar dalam merajut fakta-fakta menjadi narasi cerita yang utuh dan mengalir, dibandingkan pendekatan sekali tembak (*zero-shot*) pada *Baseline*.

## 2. Bedah Distribusi dan Signifikansi per Dimensi (G-Eval)

Analisis yang lebih presisi dilakukan dengan membedah skor global tersebut ke dalam 5 dimensi pembentuknya (skala 1-5). Hasil uji statistik merangkum temuan yang sangat bervariasi bergantung pada tuntutan struktural dari masing-masing dimensi.

### Tabel 4.3.4: Statistik Komparasi Dimensi Koherensi Naratif

| Dimensi | Baseline (Mean) | *Agentic* AI (Mean) | Delta | Nilai-p (p-value) | Cohen's d | Signifikansi (p < 0,05) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Conciseness** | 3,49 | 4,25 | +0,76 | 3,97e-12 | +1,116 | Signifikan (Efek Besar) |
| **Repetitiveness** | 3,64 | 4,58 | +0,94 | 2,49e-10 | +0,993 | Signifikan (Efek Besar) |
| **Consistency** | 4,11 | 4,53 | +0,42 | 0,0017 | +0,455 | Signifikan (Efek Sedang) |
| **Fluency** | 4,48 | 4,70 | +0,22 | 0,0548 | +0,273 | Tidak Signifikan |
| **Clarity** | 4,89 | 4,81 | -0,08 | 0,3926 | -0,123 | Tidak Signifikan |

Berdasarkan Tabel 4.3.4, terdapat tiga pola temuan utama yang mendefinisikan perbedaan kualitas karya *Baseline* dan *Agentic* AI:

1.  **Lompatan Signifikan pada Manajemen Teks (*Conciseness* & *Repetitiveness*)**
    Kelemahan terbesar *Baseline* terletak pada ketidakmampuannya mengatur kepanjangan informasi. Teks *Baseline* cenderung bertele-tele (skor *Conciseness* 3,49) dan sering mengulang fakta yang sama (*Repetitiveness* 3,64). Sistem *Agentic* AI berhasil memecahkan masalah ini dengan meroketkan skor *Conciseness* (+0,76 poin) dan menekan repetisi (+0,94 poin). Ukuran efek (Cohen's d) sebesar ~1,0 menunjukkan bahwa perbaikan pada struktur cerita ini sangat masif dan kasat mata. Agen evaluasi terbukti aktif memangkas paragraf yang membosankan (*filler*) menjadi kalimat naratif yang efektif.
2.  **Peningkatan Moderat pada Logika Cerita (*Consistency*)**
    Sistem *Agentic* AI secara konsisten mampu menahan watak karakter dan kohesi alur dari awal hingga akhir, membawa *Consistency* naik secara signifikan (p = 0,001) dengan efek sedang (d = 0,455). Model *Baseline* sering kali tersandung pada inkonsistensi internal saat cerita semakin panjang.
3.  **Batas Atas yang Membentur Langit (*Ceiling Effect* pada *Fluency* & *Clarity*)**
    Tidak terdapat perbedaan yang signifikan pada dimensi *Fluency* dan *Clarity*. Hal ini disebabkan karena model dasar yang digunakan (Gemini Flash 2.5) secara inheren sudah memiliki tata bahasa dan ejaan yang sempurna (sebagaimana didiskusikan pada anomali bias positivitas di bab sebelumnya). Skor *Clarity* pada *Baseline* telah mencapai titik jenuh (4,89 dari 5,00), sehingga sistem agen tidak memiliki ruang lagi untuk meningkatkan skor tersebut secara matematis, melainkan hanya menjaganya agar tidak turun secara drastis saat teks diubah menjadi fiksi.
