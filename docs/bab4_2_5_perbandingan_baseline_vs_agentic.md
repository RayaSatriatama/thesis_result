# 4.2.5 Perbandingan Baseline vs *Agentic* AI (Faithfulness)

Subbab ini menyajikan analisis komparatif performa kesetiaan fakta (*faithfulness*) antara sistem baseline (generasi alur tunggal biasa tanpa agen pengkritik) dan sistem *Agentic* AI (generasi berbasis kolaborasi multi-agen dengan modul *researcher-critic loop*). Evaluasi dilakukan secara kuantitatif terhadap populasi lengkap sebanyak 200 *trace* (100 *trace* baseline dan 100 *trace* *Agentic* AI). Pembahasan membedah perbedaan signifikansi statistik antara standar RAGAS dan FABLES melalui uji signifikansi non-parametrik Mann-Whitney U, ukuran efek (*effect size*) Cohen's d, serta analisis komparatif densitas dan sebaran label klaim.

---

## 1. Analisis Uji Signifikansi Statistik dan Ukuran Efek

Untuk menguji apakah peningkatan kualitas kesetiaan fakta dari sistem baseline ke sistem *Agentic* AI bersifat signifikan secara ilmiah atau sekadar variasi pengambilan sampel, dilakukan pengujian statistik non-parametrik Mann-Whitney U (satu-sisi: *Agentic* AI > *Baseline*) serta perhitungan ukuran efek *Cohen's d*. Pengujian non-parametrik dipilih karena sebaran skor *faithfulness* tidak berdistribusi normal dan memiliki kemiringan (*skewness*) yang sangat tajam menuju batas atas (*ceiling effect*).

Tabel berikut menyajikan ringkasan hasil uji signifikansi statistik perbandingan baseline vs *Agentic* AI untuk populasi keseluruhan (Semua Bahasa, N = 100 untuk masing-masing sistem):

| Metrik Evaluasi | Baseline Mean ± Std | *Agentic* AI Mean ± Std | Delta Mean (%) | p-value | Signifikansi Statistik | Cohen's d (Effect Size) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **RAGAS Standard (Strict)** | 0.8269 ± 0.1359 | 0.9262 ± 0.1073 | +0.0993 (+12.0%) | 0.0000 | Sangat Signifikan (***) | 0.811 (Besar) |
| **FABLES Faithfulness** | 0.9909 ± 0.0307 | 0.9898 ± 0.0417 | -0.0011 (-0.1%) | 0.2322 | Tidak Signifikan (ns) | -0.030 (Negligible) |

### Interpretasi Perbedaan Performa Metrik
Berdasarkan data uji signifikansi di atas, ditemukan kontras performa yang sangat tajam antara metrik RAGAS Standard dan FABLES Faithfulness:

1. **Keberhasilan Mutlak RAGAS Standard**: Sistem *Agentic* AI berhasil meningkatkan rata-rata skor RAGAS Standard Faithfulness secara sangat signifikan sebesar +12.0% (dari 0.8269 menjadi 0.9262) dengan nilai p-value sebesar 0.0000 (p < 0.001). Nilai ukuran efek *Cohen's d* tercatat sebesar 0.811, yang diklasifikasikan sebagai **efek berukuran besar (large effect size)**. Peningkatan yang luar biasa ini membuktikan bahwa integrasi modul *researcher & critic loop* berbasis agen bekerja sangat efektif dalam memaksa model pembuat cerita menyajikan cerita yang murni berpijak pada fakta dokumen sumber riset.
2. **Fenomena Efek Langit-langit (Ceiling Effect) pada FABLES**: Rata-rata skor FABLES Faithfulness untuk sistem baseline (0.9909) dan *Agentic* AI (0.9898) tercatat hampir identik, menghasilkan selisih delta yang sangat tipis (-0.1%) dan tidak signifikan secara statistik (p-value = 0.2322, *negligible effect size*). 
   * *Penjelasan Metodologis*: Ketidakmampuan FABLES mendeteksi perbaikan sistem disebabkan oleh **efek langit-langit (ceiling effect)** yang sangat ekstrem. Karena FABLES mengecualikan label *CANT_VERIFY* dan *PARTIAL_SUPPORT* dari pembilang dan penyebut matriks biner 2x2, draf cerita baseline yang memuat banyak kalimat dramatisasi tanpa bukti tetap mendapatkan skor sempurna 1.0 selama kalimat tersebut tidak bertentangan langsung (*UNFAITHFUL*) secara fatal dengan dokumen riset. FABLES gagal membedakan peningkatan kualitas penjangkaran fakta (*grounding*), sedangkan RAGAS Standard yang bersifat ketat (*strict*) sangat sensitif terhadap perubahan proporsi label non-faithful tersebut.

---

## 2. Perbandingan Karakteristik Signifikansi Lintas Bahasa (EN vs ID)

Analisis signifikansi juga dipecah berdasarkan bahasa untuk mendeteksi apakah keunggulan pendekatan berbasis agen (*Agentic* AI) konsisten terjadi pada Bahasa Inggris (EN) dan Bahasa Indonesia (ID).

Tabel berikut menyajikan ringkasan uji perbandingan lintas bahasa untuk metrik **RAGAS Standard Faithfulness**:

| Sub-Populasi Bahasa | Baseline Mean ± Std | *Agentic* AI Mean ± Std | Delta Mean | p-value | Signifikansi | Cohen's d (Effect Size) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bahasa Inggris (EN)** | 0.8126 ± 0.1322 | 0.9278 ± 0.0828 | +0.1152 (+14.2%) | 0.0000 | Sangat Signifikan (***) | 1.044 (Sangat Besar) |
| **Bahasa Indonesia (ID)** | 0.8413 ± 0.1380 | 0.9247 ± 0.1271 | +0.0834 (+9.9%) | 0.0001 | Sangat Signifikan (***) | 0.629 (Sedang) |

Tabel berikut menyajikan ringkasan uji perbandingan lintas bahasa untuk metrik **FABLES Faithfulness**:

| Sub-Populasi Bahasa | Baseline Mean ± Std | *Agentic* AI Mean ± Std | Delta Mean | p-value | Signifikansi | Cohen's d (Effect Size) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bahasa Inggris (EN)** | 0.9868 ± 0.0396 | 0.9920 ± 0.0310 | +0.0052 (+0.5%) | 0.1314 | Tidak Signifikan (ns) | 0.145 (Negligible) |
| **Bahasa Indonesia (ID)** | 0.9950 ± 0.0180 | 0.9876 ± 0.0509 | -0.0074 (-0.7%) | 0.5462 | Tidak Signifikan (ns) | -0.194 (Negligible) |

### Analisis Kesenjangan Bahasa
Berdasarkan data sebaran bahasa di atas, ditemukan dua pola kontras antara sensitivitas RAGAS Standard dan ketidakmampuan deteksi FABLES pada kedua bahasa:

1. **Peningkatan RAGAS yang Konsisten**: Peningkatan skor RAGAS Standard terbukti sangat signifikan (p < 0.001) baik untuk Bahasa Inggris maupun Bahasa Indonesia. Bahasa Inggris menunjukkan ukuran efek yang luar biasa besar (Cohen's d = 1.044) dengan kenaikan rata-rata +14.2%, sementara Bahasa Indonesia menunjukkan ukuran efek sedang menuju besar (Cohen's d = 0.629) dengan peningkatan rata-rata +9.9%. Kesenjangan ukuran efek ini mengindikasikan bahwa proses penyelarasan fakta (*factual alignment*) pada *Critic Agent* bekerja sedikit lebih presisi dalam Bahasa Inggris. Hal ini dipengaruhi oleh kemampuan dasar model fondasi (Gemini Flash 2.5) yang secara bawaan memiliki pemahaman logika instruksi dan pemrosesan semantik dokumen yang lebih matang dalam Bahasa Inggris sebagai bahasa utama pelatihan model.
2. **Efek Langit-langit FABLES pada Kedua Bahasa**: Sebaliknya, metrik FABLES gagal menunjukkan perbedaan signifikan baik pada Bahasa Inggris (p-value = 0.1314) maupun Bahasa Indonesia (p-value = 0.5462). Delta mean yang tercipta sangat kecil (+0.5% untuk EN dan -0.7% untuk ID), dengan ukuran efek yang diabaikan (*negligible*). Hal ini membuktikan bahwa fenomena efek langit-langit (*ceiling effect*) yang menimpa FABLES terjadi secara universal pada kedua bahasa, yang disebabkan oleh mekanisme perumusan skor FABLES yang secara naif mengesampingkan klaim dengan label *CANT_VERIFY* dan *PARTIAL_SUPPORT*. Model pembuat cerita cenderung menghasilkan kalimat halusinasi dramatis yang tidak bertentangan langsung dengan dokumen secara merata di kedua bahasa, sehingga FABLES selalu memberikan skor mendekati 1.0 tanpa mendeteksi pengurangan halusinasi subtil yang diukur secara presisi oleh RAGAS.

---

## 3. Perbandingan Densitas dan Distribusi Label Klaim FABLES

Analisis agregat terhadap seluruh data observasi klaim menyajikan penjelasan mekanistik di balik lonjakan skor RAGAS Standard. Data dikumpulkan dari total 100 *trace* cerita baseline dan 100 *trace* cerita *Agentic* AI.

Tabel berikut menyajikan data perbandingan jumlah total dan proporsi label klaim antara kedua sistem:

| Parameter Evaluasi Klaim | Sistem Baseline (100 Trace) | Proporsi terhadap Total | Sistem *Agentic* AI (100 Trace) | Proporsi terhadap Total | Selisih Proporsi (Agentic - Baseline) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Total Klaim FABLES** | 2.834 | 100.00% | 1.654 | 100.00% | N/A |
| **Rata-rata Klaim per Cerita** | 28.34 | N/A | 16.54 | N/A | **-41.6% (Penurunan)** |
| **FAITHFUL** | 2.363 | 83.38% | 1.538 | 92.99% | **+9.61% (Peningkatan)** |
| **UNFAITHFUL** | 20 | 0.71% | 14 | 0.85% | +0.14% |
| **CANT_VERIFY** | 262 | 9.24% | 49 | 2.96% | **-6.28% (Penurunan)** |
| **PARTIAL_SUPPORT** | 189 | 6.67% | 53 | 3.20% | **-3.47% (Penurunan)** |

### Pembahasan Temuan Mekanistik
Perbandingan distribusi klaim di atas menyajikan dua temuan ilmiah penting:

1. **Pemangkasan Densitas Klaim yang Redundan (Densitas Rendah)**:
   Sistem baseline menghasilkan rata-rata 28.34 klaim per cerita, sedangkan sistem *Agentic* AI hanya menghasilkan rata-rata 16.54 klaim (penurunan drastis sebesar 41.6% dalam volume klaim). 
   * *Sebab*: Sistem baseline yang berjalur tunggal cenderung menulis cerita yang sangat panjang, bertele-tele, dan memuat kalimat yang berulang secara faktual karena ketiadaan pengawasan. Sebaliknya, sistem *Agentic* AI mengintegrasikan peran agen supervisor (*Supervisor Agent*) dan agen pengkritik (*Critic Agent*) yang secara aktif menegakkan aturan keringkasan (*conciseness*) dan peniadaan repetisi (*repetitiveness*). Dampaknya, cerita hasil *Agentic* AI menjadi jauh lebih padat, ringkas, dan mudah dipahami oleh siswa.
2. **Pemberantasan Klaim Tanpa Bukti (CANT_VERIFY & PARTIAL_SUPPORT)**:
   Proporsi klaim *CANT_VERIFY* terpangkas secara masif dari 9.24% pada baseline menjadi hanya 2.96% pada *Agentic* AI (penurunan lebih dari 3 kali lipat). Proporsi klaim *PARTIAL_SUPPORT* juga menyusut dari 6.67% menjadi 3.20%.
   * *Sebab*: Ini adalah mekanisme utama yang mendongkrak skor RAGAS Standard. Pada sistem baseline, model bebas melakukan lompatan narasi dramatis yang memuat fakta-fakta sejarah atau nama tokoh baru yang tidak ada pada dokumen riset (sehingga bernilai *CANT_VERIFY*). Pada sistem *Agentic* AI, modul *critic loop* secara aktif mendeteksi klaim-klaim tidak berdasar tersebut. Jika draf cerita mengandung proposisi yang tidak dapat dibuktikan atau hanya didukung sebagian oleh teks hasil pencarian LightRAG, *Critic Agent* akan menolak draf tersebut dan memberikan umpan balik perbaikan. Hasilnya, cerita akhir dipaksa untuk murni bertumpu pada dokumen riset eksternal yang sah.

---

## 4. Bukti Visual Uji Signifikansi Statistik dari Streamlit

Tangkapan layar berikut menyajikan visualisasi data uji signifikansi statistik perbandingan baseline vs *Agentic* AI secara riil pada dashboard Streamlit, yang memperlihatkan kode warna hijau untuk metrik dengan peningkatan sangat signifikan (p < 0.001) serta kode warna merah untuk metrik yang tidak signifikan:

![Tabel Uji Signifikansi Statistik Baseline vs *Agentic* AI dari Streamlit](../assets/evaluation/4.2.5_baseline_vs_agentic_significance.png)
