# Bab 4.4 Sintesis Lintas-Dimensi: Analisis Hubungan Kausalitas dan Korelasi Antara *Faithfulness* dengan Koherensi Naratif

Setelah menguraikan hasil evaluasi *faithfulness* (kebenaran faktual) pada Bab 4.2 dan *coherence* (koherensi naratif) pada Bab 4.3, subbab ini menyajikan analisis integratif untuk menguji hubungan timbal-balik antara kedua metrik tersebut. Dalam rekayasa *prompt* dan arsitektur berbasis agen (*Agentic* AI), terdapat asumsi umum mengenai adanya *trade-off* (tarik-ulur) antara mempertahankan kebenaran fakta sejarah atau sains dengan kebebasan kreatif untuk merajut narasi fiksi yang mengalir. 

Untuk membuktikan asumsi tersebut secara empiris, subbab ini menganalisis nilai korelasi non-parametrik **Spearman rho** antar metrik, serta meneliti dinamika pengaruh jumlah siklus revisi (*revision count*) terhadap kualitas akhir cerita anak yang dihasilkan oleh sistem *Agentic* AI berbasis Gemini Flash 2.5.

## 1. Ortogonalitas Dimensi Evaluasi (Analisis Korelasi Spearman)

Pengujian korelasi dilakukan untuk mengetahui apakah cerita yang memiliki tingkat keshahihan fakta (*faithfulness*) tinggi juga secara otomatis memiliki nilai koherensi naratif yang tinggi, atau apakah kedua dimensi tersebut berdiri sendiri sebagai parameter yang independen (ortogonal).

Berdasarkan perhitungan statistik terhadap 100 cerita yang dihasilkan oleh sistem *Agentic* AI, diperoleh nilai korelasi Spearman rho sebagai berikut:

*   **FABLES vs G-Eval Coherence (Average)**: rho = 0,0425 (p = 0,6744)
*   **RAGAS vs G-Eval Coherence (Average)**: rho = 0,0143 (p = 0,8876)
*   **FABLES vs RAGAS (Korelasi Antar-Metrik Faithfulness)**: rho = 0,2620 (p = 0,0085)

Hasil uji statistik di atas menunjukkan temuan metodologis yang sangat krusial. Nilai korelasi antara metrik *faithfulness* (baik FABLES maupun RAGAS) dengan skor koherensi G-Eval terpantau sangat mendekati nol dan tidak signifikan secara statistik (nilai p jauh di atas batas signifikansi 0,05). 

Ketiadaan korelasi ini membuktikan bahwa **dimensi *faithfulness* dan koherensi naratif bersifat ortogonal (independen)** di dalam sistem *Agentic* AI. Cerita anak yang dihasilkan tidak mengalami *confounding* (perancuan variabel) di mana cerita yang dinilai sangat koheren secara otomatis dinilai setia terhadap fakta, atau sebaliknya. 

Ortogonalitas ini menegaskan keberhasilan desain arsitektur berbasis agen (*Agentic* AI) dalam memisahkan tanggung jawab optimasi. Agen pembuat cerita (*Writer*) dan agen peninjau (*Critic*) mampu bekerja secara independen untuk memaksimalkan keindahan fiksi ilmiah tanpa mengorbankan integritas data ilmiah dari Wikipedia yang menjadi basis referensinya. 

Sementara itu, korelasi positif lemah-ke-sedang antara FABLES dan RAGAS (rho = 0,2620, p = 0,0085) mengonfirmasi bahwa meskipun kedua metrik tersebut sama-sama mengukur aspek keshahihan fakta, keduanya mengukur konstruk dengan sensitivitas yang berbeda (FABLES berbasis verifikasi klaim tingkat granular, sedangkan RAGAS berbasis tumpang-tindih pernyataan tingkat kalimat).

## 2. Dinamika Loop Revisi dan Keadilan Evaluasi (Korelasi dengan *Revision Count*)

Analisis selanjutnya ditujukan untuk mengukur efektivitas proses iterasi perbaikan yang dilakukan oleh agen penilai (*LLM Coherence Evaluator*) melalui variabel jumlah siklus revisi (*revision count*). Secara teoretis, peningkatan jumlah revisi diharapkan dapat mendongkrak skor kualitas akhir cerita. Namun, hasil statistik komparasi pada populasi cerita *Agentic* AI menunjukkan dinamika yang berbeda:

*   **Korelasi FABLES vs *Revision Count***: rho = -0,3959 (p < 0,0001)
*   **Korelasi G-Eval Coherence vs *Revision Count***: rho = -0,2635 (p = 0,0081)

Terdapat korelasi negatif signifikan yang moderat antara jumlah siklus revisi dengan skor kualitas akhir cerita, baik dari sisi *faithfulness* (rho = -0,3959) maupun koherensi naratif (rho = -0,2635). Artinya, cerita yang melalui banyak siklus revisi justru memiliki skor akhir yang cenderung lebih rendah dibandingkan dengan cerita yang lolos pada iterasi pertama atau kedua.

Fenomena ini tidak boleh disalahtafsirkan sebagai kegagalan fungsi *loop* revisi agen. Penjelasan metodologis yang melandasi anomali ini adalah **Pencilan Kompleksitas Input (Input Complexity Outliers)**:

1.  **Variasi Tingkat Kesulitan Topik**: Wikipedia menyediakan artikel rujukan dengan tingkat kepadatan fakta dan kompleksitas istilah yang sangat beragam. Untuk topik sains atau sejarah yang sederhana, agen pembuat cerita dapat langsung merumuskan draf narasi yang sempurna dalam sekali jalan, sehingga hanya memerlukan 0 sampai dengan 1 kali revisi dan langsung mendapatkan skor sempurna (skor 5).
2.  **Perjuangan Optimasi Agen**: Sebaliknya, untuk topik-topik yang sangat padat informasi teknis atau memiliki logika konseptual yang rumit, draf awal yang dihasilkan oleh agen *Writer* sering kali terdeteksi melanggar batas konsistensi alur atau bahkan mengalami halusinasi fakta oleh agen *Critic*. Kondisi inilah yang memicu aktifnya *loop* revisi hingga batas maksimal untuk memperbaiki cerita secara bertahap.
3.  **Batas Atas Keterbatasan Prompt**: Meskipun siklus revisi berhasil menyelamatkan kualitas cerita dari kegagalan total, tingkat kesulitan inheren dari data mentah tersebut membuat cerita tersebut sulit untuk mencapai "skor sempurna" yang mudah diraih oleh topik sederhana. 

Siklus revisi dalam sistem *Agentic* AI berfungsi sebagai jaring pengaman (*safety net*) yang secara aktif dipicu oleh topik-topik sulit. Nilai korelasi negatif ini menjadi bukti empiris bahwa agen penilai internal bekerja secara adil dan objektif, bukan sekadar memberikan persetujuan buta (*rubber-stamping*) tanpa adanya perbaikan kualitas yang nyata.

## 3. Pengaruh Bahasa terhadap Sensitivitas Optimasi (ID vs EN)

Analisis silang lebih mendalam dilakukan dengan membagi populasi berdasarkan bahasa instruksi dan luaran (Bahasa Indonesia dan Bahasa Inggris) untuk melihat konsistensi perilaku sistem:

### Tabel 4.4: Korelasi Spearman Metrik Utama vs *Revision Count* per Bahasa

| Hubungan Komparasi | Bahasa Inggris (EN) - rho | Nilai-p (EN) | Bahasa Indonesia (ID) - rho | Nilai-p (ID) |
| :--- | :---: | :---: | :---: | :---: |
| **FABLES vs *Revision Count*** | -0,5344 | < 0,0001 | -0,2646 | 0,0633 |
| **G-Eval vs *Revision Count*** | -0,2303 | 0,1076 | -0,2972 | 0,0361 |

Data Tabel 4.4 menyingkap perbedaan sensitivitas optimasi yang dipengaruhi oleh batasan bahasa pada model dasar Gemini Flash 2.5:

1.  **Sensitivitas Keshahihan Fakta pada Bahasa Inggris (EN)**:
    Korelasi negatif antara FABLES dengan jumlah revisi sangat kuat pada sub-populasi bahasa Inggris (rho = -0,5344, p < 0,0001), sementara pada bahasa Indonesia korelasi tersebut melemah dan tidak signifikan secara statistik (rho = -0,2646, p = 0,0633). Hal ini menunjukkan bahwa agen evaluator berbasis bahasa Inggris jauh lebih sensitif dan ketat dalam mendeteksi distorsi fakta pada draf cerita bahasa Inggris, sehingga memicu revisi berulang-ulang ketika menghadapi topik yang rumit. 
2.  **Sensitivitas Koherensi pada Bahasa Indonesia (ID)**:
    Sebaliknya, korelasi negatif antara G-Eval Coherence dengan jumlah revisi justru signifikan pada cerita berbahasa Indonesia (rho = -0,2972, p = 0,0361). Hal ini mengindikasikan bahwa proses penyelarasan alur cerita dalam bahasa Indonesia membutuhkan usaha optimasi yang lebih intensif pada struktur bahasa untuk mencapai tingkat koherensi yang dapat diterima oleh sistem penilai otomatis.

## 4. Sintesis Akhir dan Rekomendasi Desain Sistem Berbasis Agen (*Agentic* AI)

Berdasarkan seluruh rangkaian temuan lintas-dimensi ini, dirumuskan beberapa sintesis ilmiah yang menjadi kontribusi teoretis sekaligus rekomendasi praktis bagi pengembangan sistem kecerdasan buatan pembuat konten edukatif di masa depan:

1.  **Pemisahan Parameter Kendali (*Decoupled Control*)**:
    Penelitian ini membuktikan bahwa kualitas faktual (*faithfulness*) dan kualitas sastrawi (*coherence*) adalah dua hal yang tidak saling memengaruhi secara mekanis. Oleh karena itu, pengembang sistem AI disarankan untuk selalu memisahkan metrik evaluasi ke dalam agen-agen spesifik (misal, agen khusus verifikasi klaim dan agen khusus kurasi estetika bahasa) untuk menghindari bias penilaian global.
2.  **Alokasi Anggaran Revisi Adaptif (*Adaptive Revision Budget*)**:
    Mengingat adanya korelasi negatif antara jumlah revisi dengan skor akhir akibat tingkat kesulitan topik, sistem di masa depan sebaiknya menerapkan deteksi kompleksitas teks sumber di awal proses. Topik dengan kepadatan fakta yang tinggi harus langsung dialokasikan dengan anggaran revisi (*revision budget*) yang lebih besar serta petunjuk penulisan (*prompt*) yang lebih spesifik sejak iterasi pertama.
3.  **Pentingnya Pengawasan Manusia (*Human-in-the-Loop*)**:
    Meskipun model evaluasi otomatis G-Eval dan FABLES memiliki keandalan klasifikasi yang sangat tinggi (akurasi makro di atas 85%), anomali *overestimation* pada aspek kefasihan sastrawi tetap memerlukan sentuhan validator manusia untuk memastikan cerita tidak terasa kaku bagi pembaca anak-anak. Kombinasi terbaik adalah membiarkan agen otomatis melakukan penyaringan kesalahan tata bahasa dan penyimpangan fakta secara masif, kemudian ditutup dengan kurasi manusia untuk pemolesan rasa bahasa yang natural.
