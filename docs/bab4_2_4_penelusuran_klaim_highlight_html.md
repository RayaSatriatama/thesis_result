# 4.2.4 Penelusuran Klaim dan Highlight HTML (Analisis Kualitatif)

Subbab ini menyajikan analisis kualitatif mendalam terhadap hasil penelusuran klaim kesetiaan fakta (*faithfulness*) pada sepuluh cerita sampel skripsi (lima cerita berbahasa Inggris dan lima cerita berbahasa Indonesia). Analisis dilakukan dengan memanfaatkan visualisasi antarmuka HTML interaktif pada dashboard Streamlit, yang memetakan setiap klaim cerita secara bersandingan dengan dokumen konteks hasil pencarian (*retrieval*). Pembahasan difokuskan pada verifikasi akurasi penandaan kalimat (*highlight*), fenomena kegagalan *retrieval* eksternal yang memicu klaim hanya didukung oleh rencana cerita (*Planner-only*), serta analisis mendalam terhadap penyebab rendahnya skor kesetiaan pada cerita dengan skor rendah (*Story 9* dan *Story 10*).

---

## 1. Verifikasi Manual Klaim vs Konteks Sumber (Akurasi Highlight)

Visualisasi interaktif pada dashboard membagi antarmuka menjadi dua kolom utama: kolom kiri menampilkan dokumen konteks riset (gabungan sumber riset asli dan ringkasan *Knowledge Graph* atau KG) yang dilengkapi dengan penandaan warna (*highlight*) kuning, sedangkan kolom kanan menampilkan kartu klaim FABLES beserta label keputusan evaluator.

Berdasarkan audit manual yang diselaraskan dengan validasi ahli materi, mekanisme penandaan kalimat (*highlight matching*) yang menghubungkan klaim atomik ke kalimat sumber yang relevan terbukti sangat akurat dan informatif:
* **Penanganan Parafrasa Semantik**: Mekanisme pencocokan mampu mengidentifikasi kalimat sumber meskipun cerita tidak menggunakan kata yang sama secara harfiah (literal). Sebagai contoh, pada **Story 6 (Skor Tinggi ID)**, Klaim 6 diprediksi sebagai *FAITHFUL* dan dihubungkan ke dokumen konteks riset [2]. Konteks riset [2] menyebutkan kalimat mengenai gambar bahan makanan dan ide masakan, sedangkan cerita menggunakan frasa resep masakan. Validasi ahli materi menandai kasus ini sebagai selaras sebagian (*partial notes*) secara leksikal namun tetap mendukung makna multimodal cerita secara penuh, membuktikan model pengevaluasi sensitif terhadap keselarasan semantik.
* **Koreksi Asosiasi Konservatif (False Negative)**: Audit manual oleh ahli materi membantu mengoreksi keputusan evaluator otomatis yang terlalu ketat. Sebagai contoh, pada **Story 4 (Skor Rendah EN)**, Klaim 8 (membahas 111 korban luka gempa Hormozgan) otomatis dilabeli sebagai *PARTIAL_SUPPORT* oleh evaluator FABLES karena struktur kalimat cerita yang sedikit bergeser dari kutipan aslinya. Namun, verifikasi manual membuktikan fakta angka 111 orang tersebut didukung penuh oleh kalimat pada konteks riset yang sama dengan Klaim 7. Kasus ini dihitung sebagai *False Negative* untuk mengevaluasi batas ketat otomatisasi *LLM-as-a-Judge*.

---

## 2. Fenomena Klaim Hanya Didukung Rencana Cerita (Planner-only)

Pada beberapa kasus evaluasi, ditemukan fenomena di mana klaim cerita dinyatakan tidak didukung oleh dokumen riset eksternal, namun didukung secara penuh oleh rencana cerita (*Planner Output* atau Konteks [0]) yang disusun pada tahap awal generasi. Fenomena ini dianalisis secara tajam pada **Story 8 (Skor Sedang ID - Menara Jam Chimnabai)**:

* **Karakteristik Kasus**: Beberapa klaim mengenai sejarah pembangunan dan detail fisik Menara Jam Chimnabai dilabeli sebagai *CANT_VERIFY* atau *PARTIAL_SUPPORT* terhadap dokumen riset [1]-[4] karena informasi tersebut tidak muncul pada kutipan teks riset yang ditarik oleh modul *retrieval*. Namun, informasi tersebut muncul secara eksplisit pada Konteks [0] (Rencana Cerita) karena agen perencana (*planner agent*) menyusun outline berdasarkan memori internal LLM atau garis besar instruksi awal.
* **Keterbatasan Retrieval pada Informasi Spesifik**: Kasus *Planner-only* ini menunjukkan keterbatasan mendasar dari pencarian vektor (*vector retrieval*) pada dokumen sumber yang sangat spesifik atau lokal. Jika dokumen riset yang tersedia di pangkalan data tidak memuat detail nama menara jam secara literal, modul pencarian akan gagal menarik dokumen pendukung.
* **Implikasi Metodologis**: Meskipun cerita terasa sangat runtut dan kaya akan fakta sejarah secara naratif, sistem pengevaluasi otomatis (FABLES atau RAGAS) tetap memberikan skor rendah karena membatasi basis kebenaran hanya pada dokumen riset hasil *retrieval* eksternal. Hal ini membuktikan bahwa evaluasi kesetiaan fakta otomatis sangat bergantung pada kelengkapan dan relevansi dokumen yang berhasil ditarik oleh RAG, bukan sekadar kebenaran umum internal LLM.

---

## 3. Analisis Kualitatif Cerita Skor Rendah (Story 9 dan Story 10)

Untuk memahami batasan performa sistem *Agentic AI*, analisis kualitatif dilakukan secara mendalam terhadap dua cerita yang mendapatkan skor kesetiaan terendah pada populasi cerita berbahasa Indonesia.

### A. Story 9 (Gaucho Americano - Kasus Kegagalan Retrieval Eksternal)
Cerita ini mendapatkan skor *faithfulness* yang sangat rendah (hanya 1 klaim *FAITHFUL* dari total 10 klaim). Analisis kualitatif membuktikan bahwa kegagalan ini sepenuhnya disebabkan oleh **kegagalan modul retrieval (Retrieval Failure)**, bukan halusinasi kreatif dari model penulisan cerita:
* **Mismatch Konteks**: Dokumen riset [1]-[4] yang berhasil ditarik oleh LightRAG bertema arkeologi anak di Indonesia. Namun, prompt input cerita menuntut sistem membuat kisah sejarah film *Gaucho Americano* di Chili.
* **Dampak pada Generasi**: Karena terjadi kegagalan pencarian vektor secara total, agen perencana dan agen pembuat cerita terpaksa menulis cerita berdasarkan instruksi outline (sejarah perilisannya di Chili) menggunakan pengetahuan internal LLM tanpa didukung dokumen riset yang relevan.
* **Dampak pada Evaluasi**: Model pengevaluasi otomatis membandingkan klaim cerita tentang film Chili terhadap dokumen riset tentang arkeologi anak Indonesia. Akibatnya, 9 klaim dideklarasikan sebagai tidak terverifikasi (*CANT_VERIFY* atau *PARTIAL_SUPPORT*), yang secara tepat dinilai sebagai *True Negative* oleh ahli materi karena ketiadaan bukti pendukung tekstual. Kasus *False Positive* terjadi pada Klaim 1 di mana model pengevaluasi secara keliru melabeli klaim tanggal rilis film sebagai *FAITHFUL* meskipun dokumen riset murni membahas arkeologi Indonesia.

### B. Story 10 (Roanoke Railroad - Kasus Halusinasi Model Penulisan)
Berbeda dengan Story 9, cerita Roanoke Railroad memiliki dokumen *retrieval* riset yang sangat relevan dan lengkap. Rendahnya skor kesetiaan (terdapat 2 klaim *UNFAITHFUL* mutlak) murni disebabkan oleh **kesalahan penulisan LLM (Writer Hallucination)**:
* **Analisis Kasus Klaim 6 dan 8**: Cerita menggambarkan bahwa proses penggabungan penuh (*merger*) Roanoke & Tar River Railroad (R&TRR) ke dalam maskapai penerus Seaboard Air Line (SAL) telah selesai seutuhnya pada tahun 1900. Namun, dokumen riset [1], [2], dan dokumen KG secara eksplisit menuliskan bahwa penggabungan penuh tersebut baru selesai pada tahun **1911**.
* **Penyebab Kesalahan**: Agen perencana menuliskan tahun 1900 sebagai klimaks naratif dramatis agar cerita terasa lebih padat, dan agen pembuat cerita mengikuti outline tersebut tanpa melakukan verifikasi silang terhadap teks asli.
* **Deteksi Sukses oleh Evaluator**: Kasus ini membuktikan kekuatan sistem evaluasi otomatis. Model pengevaluasi FABLES berhasil mendeteksi pertentangan tahun (1900 vs 1911) secara tepat dan melabeli kedua klaim tersebut sebagai *UNFAITHFUL* (True Negative yang dikonfirmasi oleh validasi ahli materi).

---

## 4. Bukti Visual Analisis Kualitatif dari Dashboard Streamlit

Berikut adalah bukti visual tangkapan layar langsung dari modul visualisasi penelusuran klaim pada Streamlit untuk **Story 9 (Kategori Skor Rendah ID)**. Antarmuka memperlihatkan kartu **Klaim 1 (False Positive)** dengan warna merah menyala yang memuat penjelasan kesalahan manual evaluator, serta kartu **Klaim 4 (True Negative)** berwarna hijau dengan keterangan kesesuaian label *CANT_VERIFY* oleh evaluator akibat ketiadaan informasi pada dokumen riset sebelah kiri:

![Visualisasi Kartu Evaluasi Kualitatif Klaim Story 9](../assets/evaluation/4.2.4_story09_qualitative_audit.png)
