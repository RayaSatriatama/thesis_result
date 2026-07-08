# Bab 4.3.2 Ground Truth: Validasi Ahli Bahasa

Untuk mengevaluasi keandalan model penilai otomatis (*auto-grade*) berbasis G-Eval, penelitian ini membangun acuan kebenaran (*Ground Truth*) melalui metode *expert judgment* (validasi ahli bahasa). Validasi dilakukan oleh validator ahli bahasa profesional terhadap 10 cerita sampel skripsi (5 cerita berbahasa Indonesia dan 5 cerita berbahasa Inggris). Langkah ini penting untuk menjembatani penilaian kuantitatif berbasis aturan LLM dengan kepekaan bahasa manusia yang bersifat pragmatis, kontekstual, dan pedagogis.

## 1. Instrumen Penilaian dan Pemetaan Dimensi G-Eval

Instrumen penilaian ahli bahasa terdiri atas 13 butir pernyataan kualitas kebahasaan yang dirancang khusus untuk bacaan edukasi anak. Untuk melakukan perbandingan apel-ke-apel (*apple-to-apple*) dengan evaluator otomatis G-Eval, ketiga belas butir instrumen tersebut dipetakan secara logis ke dalam lima dimensi G-Eval sebagai berikut:

1.  **Fluency (Kefasihan - Butir 1-5):**
    *   Butir 1: Ketepatan struktur kalimat.
    *   Butir 2: Ketepatan tata bahasa.
    *   Butir 3: Ketepatan ejaan.
    *   Butir 4: Kesesuaian intelektual (tingkat kesulitan kosakata bagi pembaca sasaran).
    *   Butir 5: Kesesuaian emosional (gaya bahasa yang sesuai untuk perkembangan emosi remaja).
2.  **Consistency (Konsistensi - Butir 6-7):**
    *   Butir 6: Konsistensi istilah yang digunakan.
    *   Butir 7: Konsistensi penggunaan simbol atau ikon.
3.  **Clarity (Kejelasan - Butir 8-11):**
    *   Butir 8: Kebakuan istilah kebahasaan.
    *   Butir 9: Pemahaman pesan (kemudahan pembaca dalam menyerap pesan edukasi).
    *   Butir 10: Kemampuan memotivasi (daya dorong cerita terhadap minat belajar).
    *   Butir 11: Mendorong berpikir kritis (stimulasi analitis melalui alur narasi).
4.  **Conciseness (Keringkasan - Butir 12):**
    *   Butir 12: Keefektifan kalimat (tidak bertele-tele).
5.  **Repetitiveness (Ketidak-repetitifan - Butir 13):**
    *   Butir 13: Ketidak-repetitifan (ketiadaan pengulangan frasa atau ide secara redundan).

Setiap butir diukur menggunakan skala likert 1 sampai dengan 5 (1: Sangat Kurang, 2: Kurang, 3: Cukup, 4: Baik, 5: Sangat Baik). Skor akhir untuk setiap dimensi dihitung dengan merata-ratakan skor butir-butir penyusunnya, kemudian dibulatkan ke bilangan bulat terdekat untuk menghasilkan label ordinal 1-5 yang konsisten dengan luaran G-Eval.

### Implikasi Metodologis Distribusi Bobot

Ketidakseimbangan jumlah butir antar-dimensi (seperti dimensi *Fluency* dengan 5 butir dan *Clarity* dengan 4 butir, dibandingkan *Conciseness* dan *Repetitiveness* yang hanya diwakili 1 butir) memiliki implikasi metodologis yang disengaja. Aspek *Fluency* dan *Clarity* merupakan pilar utama keberhasilan penyampaian materi sains dan teknologi kepada anak-anak. Oleh karena itu, diperlukan pengukuran yang lebih terperinci dan mendalam pada kedua dimensi tersebut untuk mendeteksi distorsi bahasa kecil yang dapat menghambat pemahaman konseptual siswa.

---

## 2. Analisis Kualitatif Masukan Validator Ahli Bahasa

Selain memberikan penilaian angka kuantitatif, validator ahli bahasa memberikan kritik dan saran kualitatif yang mendalam untuk setiap cerita sampel. Masukan ini memberikan gambaran konkret mengenai keterbatasan penulisan berbasis kecerdasan buatan dalam ranah sastra edukatif.

### A. Sub-populasi Cerita Berbahasa Indonesia (ID)

Secara umum, cerita berbahasa Indonesia dinilai memiliki struktur kebahasaan yang baik dan pesan edukasi yang sangat jelas. Namun, validator mengidentifikasi adanya kekakuan gaya bahasa naratif yang bersumber dari penerjemahan atau penalaran langsung LLM.

*   **Cerita 1 (Misteri GPT-4: Petualangan Pengetahuan Leo dan Mia):**
    Berlatar belakang fiksi ilmiah mengenai sistem AI GPT-4. Validator menyoroti kekakuan tata bahasa pada kalimat *"Itu adalah Profesor Elara..."* yang terletak di bagian klimaks cerita. Kata petunjuk "Itu" dinilai kurang tepat secara sintaksis dan disarankan untuk diganti dengan kata ganti orang seperti "dia" or "ia". Lebih lanjut, susunan redaksi kalimat secara keseluruhan pada paragraf tersebut dirasa terlalu kaku. Validator memberikan saran penyesuaian gaya bahasa agar lebih mengalir bebas (*flowing*). Terkait saran validator mengenai penyesuaian gaya bahasa dengan rentang usia tertentu, saran tersebut dinilai kurang relevan untuk ruang lingkup skripsi ini karena penelitian tidak dirancang untuk menguji kesesuaian cerita pada target usia pembaca spesifik.
*   **Cerita 2 (Petualangan Taksonomi Lebah Penyerbuk):**
    Berlatar eksplorasi ekologi tentang spesies lebah *Dasypoda radchenkoi*. Penilaian kuantitatif mutlak sempurna (skor penuh) dengan aliran narasi yang minim koreksi kualitatif.
*   **Cerita 3 (Misteri Gunung Brown):**
    Mengambil latar petualangan geografis ke Gunung Brown. Narasi dinilai cukup solid tanpa adanya kendala alur cerita yang signifikan.
*   **Cerita 4 (Petualangan Roket Raksasa: Starship Sang Penjelajah Bintang):**
    Berlatar penjelajahan ruang angkasa yang membandingkan roket Starship. Alur dinilai informatif secara teknis.
*   **Cerita 5 (Misteri Menara Jam Chimnabai):**
    Berlatar sejarah penelusuran asal-usul Menara Jam Chimnabai di masa lampau.

### B. Sub-populasi Cerita Berbahasa Inggris (EN)

Kritik terhadap cerita berbahasa Inggris lebih bervariasi dan menyoroti kelemahan struktural, inkonsistensi penokohan, serta hambatan pragmatis bagi audiens non-native di Indonesia.

*   **Cerita 1 (Mei and the Moving Museum):**
    Berlatar belakang *landmark* historis di Shanghai seperti *the Bund* dan *Nanjing Road*. Validator memberikan saran agar usia karakter utama disesuaikan guna mempermudah terbangunnya empati pembaca. Namun, saran mengenai penyesuaian usia karakter ini berada di luar fokus evaluasi penelitian karena rancangan sistem agen tidak menargetkan pengujian langsung pada kelompok usia pembaca tertentu. Dari segi konten narasi, rasa nostalgia tokoh *Grandpa Li* kurang tersampaikan secara emosional kepada pembaca karena deskripsi mengenai landmark bersejarah tersebut ditulis terlalu dangkal. Validator menyarankan penambahan fakta unik atau informasi historis mendalam tentang lokasi tersebut untuk memperkuat ikatan emosional tokoh. Selain itu, penulisan sumber rujukan ilmiah secara langsung di tengah dialog dinilai merusak keindahan fiksi ilmiah dan aliran cerita.
*   **Cerita 2 (Maya's Cosmic Quest: The PSLV-C56 Launch):**
    Berlatar belakang penelusuran jadwal peluncuran misi ruang angkasa PSLV-C56. Cerita dinilai sangat edukatif dalam memberikan panduan pencarian informasi yang akurat di dunia maya. Namun, serupa dengan cerita pertama, integrasi rujukan pustaka ke dalam teks naratif dirasa dipaksakan sehingga cerita tidak mengalir secara alami.
*   **Cerita 3 (Echoes of Resilience: Sarah's Journey to Understanding Myanmar):**
    Mengambil latar sosial krisis kemanusiaan di Myanmar. Alur cerita diapresiasi karena mampu mengembangkan sikap empati dan kepedulian sosial siswa terhadap konflik kemanusiaan global. Kendala utama tetap terletak pada metode pencantuman rujukan ilmiah langsung dalam paragraf fiksi yang dinilai mengganggu kenyamanan membaca.
*   **Cerita 4 (Alex and the PharmaCann Mystery):**
    Mengisahkan penelusuran informasi sejarah berdirinya perusahaan PharmaCann. Validator mengidentifikasi adanya celah logika (*logical gap*) pada bagian awal cerita. Karakter Alex digambarkan sangat kesulitan menemukan informasi akurat tentang legalitas medis, sementara *Professor Wise* dapat menemukannya dengan sangat mudah tanpa adanya penjelasan mengenai perbedaan teknik pencarian informasi di antara keduanya. Ketiadaan kontras metodologis ini mengurangi nilai edukasi cerita. Masukan mengenai gangguan aliran cerita akibat pencantuman rujukan langsung juga kembali ditekankan.
*   **Cerita 5 (Maya's Big Interview):**
    Berlatar belakang persiapan wawancara tokoh bisnis dari FoodFutureCo. Validator menemukan redundansi penamaan tokoh di mana nama karakter utama ("Maya") sama dengan nama tokoh pada Cerita 2 EN, sehingga disarankan untuk menggunakan variasi nama lain. Bahasa Inggris yang digunakan disarankan untuk disederhanakan karena dinilai terlalu rumit bagi pembaca pemula di Indonesia. Terdapat pula kerancuan tata bahasa pada penggunaan kata ganti *"her"* untuk tokoh Andy Simon yang memicu kebingungan gender tokoh.

---

## 3. Analisis Kuantitatif Perbandingan Ground Truth vs Prediksi (G-Eval)

Berdasarkan hasil pencocokan exact match antara label Ground Truth (GT) ahli bahasa dengan prediksi penilaian otomatis G-Eval pada 10 cerita sampel skripsi, diperoleh data komparasi skor kebahasaan (ordinal skala 1-5) yang dijabarkan pada tabel berikut:

### Tabel 4.3.2a: Perbandingan Skor GT vs Prediksi G-Eval (Bahasa Indonesia)

| Judul Cerita (ID) | Aspek Fluency (GT / Pred) | Aspek Consistency (GT / Pred) | Aspek Clarity (GT / Pred) | Aspek Conciseness (GT / Pred) | Aspek Repetitiveness (GT / Pred) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Cerita 1:** Misteri GPT-4 | 3 / 5 | 5 / 5 | 5 / 5 | 5 / 5 | 5 / 5 |
| **Cerita 2:** Lebah Penyerbuk | 3 / 5 | 5 / 5 | 5 / 5 | 5 / 5 | 5 / 5 |
| **Cerita 3:** Gunung Brown | 3 / 5 | 5 / 5 | 5 / 5 | 4 / 4 | 5 / 5 |
| **Cerita 4:** Starship | 3 / 3 | 3 / 3 | 5 / 5 | 4 / 4 | 3 / 3 |
| **Cerita 5:** Jam Chimnabai | 3 / 5 | 3 / 3 | 5 / 5 | 4 / 4 | 3 / 3 |

### Tabel 4.3.2b: Perbandingan Skor GT vs Prediksi G-Eval (Bahasa Inggris)

| Judul Cerita (EN) | Aspek Fluency (GT / Pred) | Aspek Consistency (GT / Pred) | Aspek Clarity (GT / Pred) | Aspek Conciseness (GT / Pred) | Aspek Repetitiveness (GT / Pred) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Cerita 1:** Moving Museum | 4 / 5 | 5 / 5 | 5 / 5 | 4 / 4 | 5 / 5 |
| **Cerita 2:** Cosmic Quest | 4 / 5 | 5 / 5 | 5 / 5 | 4 / 4 | 5 / 5 |
| **Cerita 3:** Echoes Myanmar | 4 / 5 | 5 / 5 | 5 / 5 | 4 / 4 | 5 / 5 |
| **Cerita 4:** PharmaCann | 3 / 3 | 3 / 3 | 1 / 1 | 4 / 4 | 3 / 3 |
| **Cerita 5:** Big Interview | 3 / 3 | 3 / 3 | 5 / 5 | 3 / 3 | 3 / 3 |

---

## 4. Temuan Penting dan Diskusi Teoretis

Analisis silang kuantitatif pada tabel-tabel di atas memunculkan beberapa fenomena penting terkait reliabilitas sistem evaluasi kebahasaan otomatis berbasis agen:

### A. Akurasi Sempurna pada Dimensi Konsistensi, Kejelasan, Keringkasan, dan Repetisi

Data kuantitatif menunjukkan kesamaan mutlak (100% *Exact Match Accuracy*) antara penilaian validator ahli dengan model penilai otomatis G-Eval pada dimensi *Consistency*, *Clarity*, *Conciseness*, dan *Repetitiveness* di seluruh cerita sampel (baik bahasa Indonesia maupun Inggris). Hal ini membuktikan bahwa kerangka kerja G-Eval yang dirancang menggunakan pendekatan *Chain-of-Thought* (CoT) memiliki keandalan yang sangat tinggi dalam mengukur aspek kebahasaan objektif. 

Sebagai contoh paling ekstrem, G-Eval berhasil mengidentifikasi penurunan kualitas kejelasan konseptual pada *Story 4 EN (Alex and the PharmaCann Mystery)* dengan memberikan skor *Clarity* terendah sebesar 1 (Sangat Kurang), yang sangat selaras dengan temuan ahli bahasa mengenai adanya celah logika pembelajaran konseptual yang membingungkan siswa.

### B. Penyimpangan Sistematis (*Overestimation*) pada Dimensi Fluency

Meskipun empat dimensi kebahasaan mencatat akurasi sempurna, dimensi *Fluency* (Kefasihan) menunjukkan pola penyimpangan sistematis berupa kelebihan penilaian (*overestimation*) oleh G-Eval. Pada 6 dari 10 cerita sampel (3 cerita ID dan 3 cerita EN), G-Eval memberikan skor sempurna 5, sedangkan penilaian dari validator ahli hanya berada pada skor 3 atau 4.

Penjelasan teoretis dan metodologis dari fenomena ini terletak pada perbedaan mendasar dari objek yang diukur oleh kedua metode evaluasi tersebut:

1.  **Kefasihan Sintaksis vs Estetika Naratif:**
    G-Eval menilai kefasihan bahasa berdasarkan ketepatan tata bahasa murni, ketiadaan kesalahan ketik, sintaksis yang benar, serta kekayaan kosakata umum yang mudah dipenuhi oleh LLM modern seperti Gemini Flash 2.5. Di sisi lain, validator manusia menilai dimensi *Fluency* dengan mempertimbangkan keluwesan ekspresi sastrawi dan kecocokan rasa bahasa untuk cerita fiksi edukatif.
2.  **Sensitivitas Gaya Bahasa Edukatif:**
    Bahasa yang secara tata bahasa baku bernilai sempurna oleh G-Eval sering kali dirasakan kaku, dingin, dan kurang mengalir (*natural flow*) oleh validator manusia (seperti kasus kesalahan diksi *"Itu adalah Profesor Elara"*). Validator ahli memberikan nilai 3 (Cukup) untuk merefleksikan bahwa meskipun teks bebas dari kesalahan gramatikal, gaya bahasa yang digunakan masih terasa kaku untuk sebuah narasi edukasi.

Temuan ini memberikan kontribusi teoretis penting bagi penelitian evaluasi LLM, yakni penilaian kebahasaan otomatis (LLM-as-a-Judge) sangat efektif untuk mengukur aspek objektif seperti konsistensi dan redundansi, namun tetap membutuhkan pengawasan ahli manusia (*human-in-the-loop*) dalam menilai aspek kebahasaan subjektif dan estetika gaya bahasa naratif.

### C. Penyelarasan Kualitatif-Kuantitatif dan Metrik Evaluasi (F1-Score)

Analisis mendalam menunjukkan adanya keselarasan (*alignment*) yang sangat presisi antara masukan kualitatif (komentar validator) dengan hasil nilai kuantitatif yang diberikan pada setiap butir penilaian. Sebagai contoh, pada *Story 4 EN (Alex and the PharmaCann Mystery)*, komentar kualitatif validator mengenai adanya "celah logika" konseptual secara langsung terefleksikan pada penjatuhan skor terendah untuk butir *Clarity* (Kejelasan), yaitu dengan skor 1 (Sangat Kurang). Keselarasan ini membuktikan bahwa instrumen evaluasi dan validator ahli memiliki konsistensi internal yang tinggi.

Secara agregat, komparasi performa klasifikasi G-Eval melawan *Ground Truth* ahli bahasa untuk 5 dimensi pada 10 cerita sampel (50 titik data komparasi) mencatatkan tingkat akurasi yang sangat baik sebesar **86,0%** dengan nilai Macro F1-Score sebesar **88,7%**. Tingginya metrik evaluasi (F1-Score) ini memberikan afirmasi kuantitatif bahwa instrumen LLM-as-a-Judge (G-Eval) secara umum mampu mereplikasi ketajaman penilaian linguistik manusia pada hampir seluruh dimensi objektif bacaan edukatif. Satu-satunya sumber deviasi hanyalah penyimpangan sistematis pada dimensi *Fluency* akibat adanya perbedaan titik berat teoretis (kefasihan sintaksis murni berbanding dengan tuntutan keluwesan estetika sastra edukatif) seperti yang telah diuraikan.
