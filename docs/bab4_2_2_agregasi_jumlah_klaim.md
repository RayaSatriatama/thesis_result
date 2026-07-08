# 4.2.2 Agregasi Jumlah Klaim per Label

Subbab ini menyajikan analisis agregat terhadap data klaim kesetiaan fakta (*faithfulness*) yang diekstrak dari seluruh *trace* cerita pada ekspor terbaru. Analisis agregat ini bertujuan untuk memetakan karakteristik sebaran data pada tingkat klaim, yang merupakan unit terkecil dalam pengujian kesetiaan fakta. Evaluasi tingkat klaim ini mencakup analisis terhadap total 1.535 klaim yang diekstrak dari populasi 100 cerita (50 cerita berbahasa Inggris dan 50 cerita berbahasa Indonesia). Pembahasan difokuskan pada komposisi empat label utama (*FAITHFUL*, *UNFAITHFUL*, *PARTIAL_SUPPORT*, dan *CANT_VERIFY*), perbandingan sebaran label antar bahasa (Inggris vs Indonesia), serta analisis variasi jumlah klaim per cerita beserta faktor-faktor yang mempengaruhinya.

---

## 1. Komposisi Empat Label Klaim Populasi

Dari total 1.535 klaim yang berhasil diekstrak dan dievaluasi secara otomatis oleh model *LLM-as-a-Judge*, komposisi masing-masing label menyajikan peta kualitas kesetiaan fakta sistem *Agentic AI* secara makro.

Tabel berikut menyajikan data agregasi jumlah klaim berdasarkan empat label utama untuk seluruh populasi (100 *trace*):

| Label Evaluasi | Jumlah Klaim (Keseluruhan) | Persentase terhadap Total Klaim | Karakteristik Kualitas Fakta |
| :--- | :---: | :---: | :--- |
| **FAITHFUL** | 1.422 | 92.64% | Didukung penuh oleh bukti teks retrieval |
| **UNFAITHFUL** | 14 | 0.91% | Bertentangan langsung dengan bukti teks |
| **PARTIAL_SUPPORT** | 50 | 3.26% | Didukung sebagian / mengandung ekstrapolasi |
| **CANT_VERIFY** | 49 | 3.19% | Tidak memiliki informasi pembuktian pada teks |
| **Total** | **1.535** | **100.00%** | **Representasi data tingkat klaim** |

### Analisis Proporsi dan Dominasi Label
Berdasarkan data tabel di atas, label **FAITHFUL** mendominasi secara mutlak dengan proporsi mencapai 92.64% dari total klaim keseluruhan. Dominasi yang sangat masif ini mengindikasikan bahwa sebagian besar proposisi faktual yang disajikan di dalam cerita hasil generasi sistem *Agentic AI* memiliki keselarasan yang sangat tinggi terhadap konteks riset eksternal. Keberhasilan ini didorong oleh integrasi modul pencarian informasi (*retrieval*) berbasis LightRAG dan proses revisi mandiri oleh agen pengkritik (*critic agent*) yang mampu memotong dan merevisi draf cerita sebelum diluncurkan ke pengguna.

Di sisi lain, proporsi kelas **UNFAITHFUL** tercatat sangat rendah, yaitu hanya 0.91% (14 klaim dari 1.535). Nilai ini membuktikan bahwa kesalahan fakta fatal berupa pertentangan langsung (halusinasi murni) berhasil ditekan hingga di bawah batas 1% pada tingkat klaim. Kelas **PARTIAL_SUPPORT** (3.26%) dan **CANT_VERIFY** (3.19%) mewakili kategori tingkat menengah di mana cerita mengandung informasi tambahan untuk kepentingan dramatisasi atau kelancaran narasi. Informasi tersebut tidak salah secara langsung, namun sulit divalidasi secara ketat karena ketiadaan fakta tekstual langsung pada dokumen sumber. Penggabungan seluruh kelas non-faithful (*UNFAITHFUL*, *PARTIAL_SUPPORT*, dan *CANT_VERIFY*) hanya menyumbang 7.36% (113 klaim) dari total dataset klaim, menunjukkan tingkat integritas faktual yang sangat kokoh secara agregat.

---

## 2. Perbandingan Karakteristik Klaim Antar Bahasa (EN vs ID)

Evaluasi juga dilakukan untuk menguji konsistensi kualitas kesetiaan fakta pada dua bahasa yang didukung oleh sistem (Bahasa Inggris dan Bahasa Indonesia). Analisis ini penting untuk mendeteksi adanya kesenjangan performa sistem akibat kendala pemrosesan bahasa alami atau perbedaan kualitas dokumen riset.

Tabel berikut menyajikan data perbandingan agregasi klaim antara Bahasa Inggris (EN) dan Bahasa Indonesia (ID):

| Parameter / Label | Sub-Populasi Bahasa Inggris (EN) | Persentase (EN) | Sub-Populasi Bahasa Indonesia (ID) | Persentase (ID) | Selisih Proporsi (ID - EN) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **FAITHFUL** | 709 | 93.41% | 713 | 91.88% | -1.53% |
| **UNFAITHFUL** | 6 | 0.79% | 8 | 1.03% | +0.24% |
| **PARTIAL_SUPPORT** | 22 | 2.90% | 28 | 3.61% | +0.71% |
| **CANT_VERIFY** | 22 | 2.90% | 27 | 3.48% | +0.58% |
| **Total Klaim** | **759** | **100.00%** | **776** | **100.00%** | **N/A** |
| **Jumlah Cerita** | **50** | **N/A** | **50** | **N/A** | **N/A** |

### Analisis Kesenjangan Bahasa
Berdasarkan data perbandingan bahasa di atas, ditemukan beberapa karakteristik penting:
1. **Kerapatan Ekstraksi Klaim yang Seimbang**: Total klaim yang diekstrak pada cerita berbahasa Inggris (759 klaim) sangat berimbang dengan cerita berbahasa Indonesia (776 klaim). Keseimbangan ini membuktikan bahwa panjang cerita dan kerapatan proposisi informasi yang dihasilkan oleh sistem memiliki konsistensi yang sangat tinggi lintas bahasa.
2. **Kelebihan Performa Bahasa Inggris**: Proporsi klaim *FAITHFUL* pada Bahasa Inggris (93.41%) tercatat sedikit lebih tinggi (+1.53%) dibandingkan dengan Bahasa Indonesia (91.88%). Hal ini selaras dengan performa dasar model LLM (GPT-4o) yang secara bawaan memiliki pemahaman semantik dan penyelarasan fakta (*factual alignment*) yang lebih tajam pada Bahasa Inggris sebagai bahasa utama pelatihan model.
3. **Karakteristik Narasi Bahasa Indonesia**: Cerita berbahasa Indonesia memiliki kecenderungan sedikit lebih tinggi untuk memuat klaim tingkat menengah *PARTIAL_SUPPORT* (3.61% vs 2.90%) dan *CANT_VERIFY* (3.48% vs 2.90%). Temuan ini menunjukkan bahwa ketika menulis cerita dalam Bahasa Indonesia, LLM cenderung melakukan lebih banyak parafrasa kreatif atau dramatisasi naratif yang memperluas konteks melampaui kutipan harfiah dokumen *retrieval*. Hal ini berimplikasi pada meningkatnya jumlah klaim yang tidak dapat diverifikasi secara tegas oleh model pengevaluasi otomatis, meskipun tidak melanggar fakta secara fatal.

---

## 3. Distribusi Jumlah Klaim per Cerita

Meskipun nilai rata-rata agregat memberikan gambaran umum, jumlah klaim yang diekstrak dari setiap cerita menunjukkan variasi individu yang sangat lebar.

Tabel berikut menyajikan ringkasan statistik deskriptif untuk sebaran jumlah klaim per cerita (N = 100):

| Sub-Populasi | Jumlah Cerita | Mean Klaim | Median | Std Dev | Minimum | Maksimum |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Keseluruhan (All)** | 100 | 15.35 | 14.00 | 9.09 | 3 | 58 |
| **Bahasa Inggris (EN)** | 50 | 15.18 | 12.50 | 9.66 | 3 | 58 |
| **Bahasa Indonesia (ID)** | 50 | 15.52 | 14.50 | 8.58 | 3 | 43 |

### Analisis Variabilitas dan Faktor yang Mempengaruhi
Sebaran jumlah klaim per cerita memiliki standar deviasi sebesar 9.09 untuk keseluruhan populasi, dengan nilai minimum 3 klaim dan nilai maksimum mencapai 58 klaim. Hal ini mengindikasikan adanya variasi yang sangat signifikan antar cerita. Variasi ini dipengaruhi oleh tiga faktor utama:

1. **Panjang Cerita (Word Count / Sentence Count)**: Karena klaim atomik diekstrak langsung dari setiap kalimat cerita, cerita yang memiliki jumlah kata atau kalimat yang lebih banyak secara linear akan menghasilkan jumlah klaim yang lebih besar. Sebagai contoh, cerita berbahasa Inggris dengan jumlah klaim maksimum (58 klaim) merupakan cerita panjang dengan struktur paragraf yang kaya dan narasi yang bertele-tele.
2. **Kerapatan Fakta (Factual Density)**: Cerita yang membahas topik-topik ilmiah yang sarat dengan informasi teknis, angka, tanggal, dan nama spesifik (seperti sejarah arkeologi atau fenomena alam) secara alami memicu LLM untuk menghasilkan proposisi faktual yang padat. Setiap kalimat pada topik ini dapat memuat dua hingga tiga klaim atomik yang berbeda. Sebaliknya, cerita yang bersifat petualangan atau fiksi deskriptif yang lebih berfokus pada emosi tokoh dan dialog memiliki kerapatan fakta yang sangat rendah, sehingga menghasilkan jumlah klaim minimum (3 klaim).
3. **Kompleksitas Topik Riset**: Kedalaman informasi yang berhasil ditarik oleh modul *retrieval* LightRAG memengaruhi bahan mentah cerita. Topik dengan dokumen sumber yang kaya akan data faktual memberikan ruang bagi agen perencana (*planner agent*) untuk menyusun draf cerita yang padat informasi, yang pada akhirnya diekstrak menjadi banyak klaim kesetiaan fakta.

---

## 4. Bukti Visual Agregasi Klaim dari Streamlit

Tangkapan layar berikut menyajikan data agregasi jumlah klaim per label secara lengkap dan interaktif pada dashboard Streamlit, yang mencakup ringkasan total klaim per bahasa (keseluruhan, Inggris, dan Indonesia):

![Tabel Agregasi Jumlah Klaim per Label dari Dashboard Streamlit](../assets/evaluation/4.2.2_claim_label_aggregation.png)
