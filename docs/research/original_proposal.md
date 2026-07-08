### PROPOSAL PENELITIAN

### ANALISIS KINERJA KOHERENSI NARATIF DAN FAITHFULNESS

**PADA SISTEM** **_AGENTIC Al_** **DAN** **_LIGHTRAG_** **UNTUK PEMBELAJARAN
BERBASIS CERITA**
_diajukan untuk memenuhi sebagian syarat untuk memperoleh gelar Sarjana
Komputer Program Studi Rekayasa Perangkat Lunak_

```
Oleh
Mohammad Raya Satriatama
NIM 2206418
```
```
PROGRAM STUDI S1 REKAYASA PERANGKAT LUNAK
KAMPUS CIBIRU
UNIVERSITAS PENDIDIKAN INDONESIA
2025
```

## DAFTAR ISI


-
- DAFTAR ISI
- DAFTAR TABLE
- DAFTAR GAMBAR
- BAB 1 PENDAHULUAN
   - 1.1 Latar Belakang Masalah
   - 1.2 Rumusan Masalah
   - 1.3 Tujuan Penelitian
   - 1.4 Manfaat Penelitian
   - 1.5 Ruang Lingkup dan Batasan Penelitian
   - 1.6 Struktur Organisasi Skripsi
- BAB 2 KAJIAN PUSTAKA
   - 2.1 Pembelajaran Berbasis Cerita
   - 2.2 Large Language Models (LLM)
   - 2.3 Retrieval-Augmented Generation (RAG)
   - 2.4 Knowledge Graph (KG)
   - 2.5 LightRAG
   - 2.6 Agentic AI
   - 2.7 Halusinasi dan Faithfulness
   - 2.8 Inkoherensi Naratif dan Koherensi Naratif
   - 2.9 State-of-The-Art
- BAB 3 METODOLOGI
   - 3.1 Desain Penelitian
      - 3.1.1 Research Clarification
      - 3.1.2 Descriptive Study I
      - 3.1.3 Prescriptive Study
      - 3.1.4 Descriptive Study II
   - 3.2 Populasi dan Sampel
   - 3.3 Instrumen Penelitian
      - 3.3.1 Story Coherence and Retrieval Enhancement (SCORE)
      - 3.3.2 Retrieval-Augmented Generation Assessment (RAGAS)
   - 3.4 Prosedur Penelitian
-
   - 3.5 Analisis Data
- DAFTAR PUSTAKA


3

### DAFTAR TABEL

Tabel 1.1 _State-of-the-Art_ ...................................................................................... 15


4

### DAFTAR GAMBAR

Gambar 3.1 DRM .............................................................................................................. 18


```
5
```
### BAB 1

### PENDAHULUAN

**1.1 Latar Belakang Masalah**
Pembelajaran berbasis cerita ( _story-based learning_ ) telah diakui sebagai
metode pedagogis yang efektif. Pendekatan ini memfasilitasi koneksi emosional
dan personal pembelajar terhadap materi, sehingga mampu mengurangi kesan kaku
atau abstrak pada konten pembelajaran (Su et al., 2021). Dalam konteks era digital,
potensi metode naratif ini menjadi semakin signifikan untuk meningkatkan
keterlibatan pengguna pada platform pembelajaran daring. Sebuah narasi yang
dirancang dengan baik dapat berfungsi menjembatani pengetahuan baru dengan
pengalaman personal pembelajar, yang tidak hanya menjadikan proses belajar lebih
bermakna, tetapi juga mengembangkan kapasitas pemahaman naratif mereka.
Sejalan dengan kebutuhan akan konten naratif tersebut, kemunculan _Large
Language Models_ (LLM) menawarkan kapabilitas tinggi dalam generasi teks yang
kompleks dan natural (Zhang et al., 2022). Meskipun demikian, pemanfaatan LLM
untuk generasi narasi skala panjang, misalnya untuk modul pembelajaran,
menghadapi dua tantangan utama. Pertama, fenomena halusinasi berupa tendensi
model untuk menghasilkan informasi yang terdengar meyakinkan, namun secara
faktual tidak benar atau tidak berdasar pada materi sumber. Dalam konteks edukasi,
halusinasi memiliki risiko tinggi karena dapat menyebabkan disinformasi atau
penyebaran konsep yang keliru (Zhang et al., 2022). Kedua, inkoherensi naratif,
yang terjadi ketika alur cerita gagal mempertahankan konsistensi internal. Model
_Artificial Intelligence_ (AI) mungkin tidak dapat melacak detail karakter atau plot
dari segmen teks sebelumnya, sehingga menghasilkan narasi yang membingungkan
dan pada akhirnya mengurangi efektivitas edukasi dari cerita tersebut
(Ammanabrolu et al., 2021).
Untuk mengatasi tantangan halusinasi dan inkoherensi, penelitian telah
mengembangkan beberapa pendekatan arsitektur inovatif. _Retrieval-Augmented
Generation_ (RAG) diperkenalkan sebagai solusi awal untuk mendasarkan
( _grounding_ ) LLM pada basis pengetahuan eksternal, yang bertujuan mengurangi
halusinasi dengan menyediakan fakta terverifikasi sebelum generasi teks (Zhang et
al., 2022). Akan tetapi, RAG tradisional yang bergantung pada representasi data


datar ( _flat data representation_ ) seringkali gagal menangkap hubungan
interdependensi yang kompleks dan cenderung menghasilkan respons yang
terfragmentasi (Guo et al., 2024). Sebagai pengembangan lebih lanjut, kerangka
kerja LightRAG secara eksplisit mengintegrasikan struktur _Knowledge Graph_
(KG) ke dalam proses pengindeksan dan _retrieval_ (Guo et al., 2024). Dengan
memodelkan entitas dan relasi dalam KG, LightRAG memungkinkan proses
pengambilan konteks yang lebih kaya serta pemahaman hubungan yang lebih
bernuansa (Guo et al., 2024; S. Ji et al., 2022). Paradigma _Agentic AI_ kemudian
melengkapi arsitektur ini. Berbeda dari _AI Agents_ konvensional yang bersifat
modular dan spesifik pada tugas tertentu, _Agentic AI_ merepresentasikan pergeseran
menuju sistem yang memiliki karakteristik otonomi terkoordinasi, dekomposisi
tugas dinamis, serta kapabilitas untuk merencanakan, memanfaatkan alat ( _tool use_ ),
dan melakukan refleksi diri ( _self-reflection_ ) dalam proses multi-langkah untuk
mencapai tujuan kompleks (Hosseini & Seilani, 2025). Dalam pendekatan ini, AI
dapat bertindak sebagai agen otonom yang memanfaatkan _retriever_ LightRAG
sebagai alat untuk mencapai tujuan naratif yang koheren.
Meskipun banyak penelitian telah berfokus pada rancang bangun sistem
hibrida yang menggabungkan LLM dan KG seperti LightRAG (Guo et al., 2024),
serta pengembangan paradigma _Agentic AI_ (Hosseini & Seilani, 2025), masih
terdapat kesenjangan signifikan dalam analisis kinerjanya. Kesenjangan ini
terutama berkaitan dengan kurangnya analisis kuantitatif yang mendalam untuk
aplikasi kreatif, seperti generasi cerita pembelajaran (Ammanabrolu et al., 2021;
Zhang et al., 2022). Sebagian besar evaluasi yang ada masih bersifat subjektif atau
menggunakan metrik umum yang tidak secara spesifik mengukur kualitas naratif.
Oleh karena itu, kebaruan penelitian ini terletak pada analisis empiris terhadap
arsitektur hibrida _Agentic AI_ dan LightRAG. Analisis ini dilakukan dengan
mengukur dua dimensi kinerja yaitu, koherensi naratif yang menilai kemampuan
sistem dalam mempertahankan alur cerita yang logis dan terstruktur, yang secara
spesifik menargetkan masalah inkoherensi dan _Faithfulness_ , yang mengukur
kemampuan sistem untuk tetap setia pada fakta yang disajikan dalam KG, yang
secara langsung menargetkan masalah halusinasi. Penelitian ini diharapkan dapat
memberikan wawasan empiris mengenai tingkat kinerja dalam menghasilkan cerita


pembelajaran yang berkualitas tinggi.

**1.2 Rumusan Masalah**
Berdasarkan latar belakang masalah, berikut adalah rumusan masalah
yang didapatkan.

1. Bagaimana kinerja koherensi naratif sistem _agentic_ AI yang diintegrasikan
    dengan LightRAG dalam menghasilkan konten pembelajaran berbasis
    cerita?
2. Bagaimana kinerja _faithfulness_ sistem _agentic_ AI yang diintegrasikan
    dengan LightRAG dalam menghasilkan konten pembelajaran berbasis
    cerita?

**1.3 Tujuan Penelitian**
Berdasarkan rumusan masalah, berikut paparan dari tujuan penelitian yang
akan dilakukan.

1. Menganalisis dan mengukur kinerja sistem _agentic_ AI dan LightRAG dari
    segi koherensi naratif.
2. Menganalisis dan mengukur kinerja sistem _agentic_ AI dan LightRAG dari
    segi _faithfulness_.

**1.4 Manfaat Penelitian**
Penelitian ini diharapkan dapat memberikan manfaat teoretis dan praktis
sebagai berikut:

1. Manfaat Teoretis:
    a. Memberikan kontribusi pada literatur evaluasi sistem AI, khususnya
       untuk arsitektur hibrida Agentic-RAG dalam domain kreatif.
    b. Memperkaya kajian di bidang teknologi pendidikan tentang penerapan
       AI untuk pengembangan konten pembelajaran.
2. Manfaat Praktis:
    a. Menjadi rujukan bagi pengembang aplikasi edukasi dalam merancang
       sistem generasi cerita yang lebih andal, koheren, dan bebas dari
       halusinasi.
    b. Memberikan wawasan bagi para pendidik dan desainer instruksional
       mengenai potensi dan batasan penggunaan AI generatif sebagai alat


```
bantu pembelajaran.
```
**1.5 Ruang Lingkup dan Batasan Penelitian**
Penelitian ini memiliki lingkup dan batasan yang ditetapkan sebagai berikut.

1. Ruang Lingkup:
    a. Sistem yang dianalisis dibangun menggunakan arsitektur _Agentic_ AI
       yang berinteraksi dengan kerangka kerja LightRAG.
    b. _Knowledge Graph_ yang digunakan sebagai basis pengetahuan dibangun
       dari korpus cerita spesifik.
    c. Analisis kinerja terbatas pada dua metrik kuantitatif yaitu, koherensi
       naratif dan _faithfulness_.
    d. Evaluasi dilakukan secara otomatis menggunakan pendekatan _LLM-as-_
       _a- judge_ terhadap set data evaluasi yang telah disiapkan.
2. Batasan Penelitian:
    a. Penelitian ini tidak melibatkan uji coba dengan pengguna akhir untuk
       mengukur dampak pedagogis secara langsung seperti tingkat
       keterlibatan atau hasil belajar.
    b. Penelitian ini tidak melakukan analisis komparatif dengan arsitektur
       RAG lainnya (misalnya, RAG berbasis vektor tradisional), melainkan
       berfokus pada analisis kinerja sistem yang diusulkan.

**1.6 Struktur Organisasi Skripsi**
Berdasarkan pedoman Penulisan Karya Ilmiah UPI Tahun 2019 yang di
himpun dalam Peraturan Rektor Universitas Pendidikan Indonesia Nomor
7867/UN40/HK/2019 struktur organisasi skripsi ini disusun sebagai berikut:

1. BAB I PENDAHULUAN: Menjelaskan konteks penelitian yang mencakup
    latar belakang masalah, rumusan masalah, tujuan penelitian, manfaat
    penelitian, ruang lingkup dan batasan penelitian, serta sistematika
    penulisan.
2. BAB II KAJIAN PUSTAKA: Menguraikan landasan teoretis yang
    mencakup konsep-konsep inti seperti Pembelajaran Berbasis Cerita, _Agentic_
    AI, _Retrieval-Augmented Generation_ (RAG), _Knowledge Graph_ , arsitektur
    LightRAG, serta definisi operasional dari metrik evaluasi koherensi naratif


```
dan faithfulness.
```
3. BAB III METODOLOGI PENELITIAN: Menjabarkan secara rinci
    langkah-langkah penelitian yang dilakukan, meliputi desain arsitektur
    sistem, prosedur pembangunan Knowledge Graph, pembuatan set data
    evaluasi, desain skenario pengujian, serta teknik analisis data untuk
    mengukur kedua metrik kinerja.
4. BAB IV HASIL DAN PEMBAHASAN: Menyajikan hasil analisis
    kuantitatif dari pengukuran kinerja Koherensi Naratif dan Faithfulness.
    Hasil tersebut kemudian dibahas secara mendalam untuk
    menginterpretasikan temuan dan menjawab pertanyaan penelitian.
5. BAB V KESIMPULAN DAN SARAN: Merangkum keseluruhan hasil
    penelitian, menyajikan kesimpulan yang ditarik dari pembahasan, serta
    memberikan saran untuk pengembangan sistem dan penelitian lebih lanjut
    di masa depan.

##


```
10
```
### BAB 2

### KAJIAN PUSTAKA

**2.1 Pembelajaran Berbasis Cerita**
Pembelajaran Berbasis Cerita ( _Story-Based Learning_ atau SBL) merupakan
pendekatan pedagogis yang mengintegrasikan narasi dan storytelling secara
terstruktur ke dalam pengalaman belajar. Metode ini memanfaatkan kekuatan narasi
sebagai medium utama untuk menyampaikan konten pembelajaran, di mana cerita
berfungsi sebagai konteks yang menghubungkan materi pembelajaran dengan
pengalaman hidup peserta didik untuk memfasilitasi pemahaman yang lebih
mendalam. Inti dari pendekatan ini adalah penggunaan komponen naratif yang
dirancang untuk melibatkan peserta didik secara emosional, yang pada gilirannya
menciptakan sistem terpadu untuk pengembangan keterampilan dan kompetensi
baru (Mawasi et al., 2021).
Efektivitas SBL didasarkan pada beberapa prinsip fundamental. Prinsip
utamanya adalah penciptaan keterlibatan emosional, di mana narasi yang kaya
menuntut peserta didik terlibat secara afektif melalui berbagai aktivitas, sehingga
memperkuat koneksi dengan materi dan meningkatkan retensi (Mawasi et al.,
2021). Prinsip penting lainnya adalah kontekstualisasi materi pembelajaran, yang
menggunakan narasi untuk menghubungkan konsep-konsep abstrak dengan
pengalaman relevan. Prinsip-prinsip pendukung lainnya mencakup fasilitasi
pembelajaran aktif dan refleksi melalui proses seperti digital storytelling (Kim et
al., 2021), serta penerapan struktur naratif yang terorganisir untuk memastikan
tercapainya tujuan pembelajaran.
Efektivitas narasi sebagai alat pembelajaran didasarkan pada
kemampuannya untuk meningkatkan keterlibatan dan pemahaman secara simultan.
Secara kognitif, struktur cerita dinilai selaras dengan cara alami otak manusia
memproses dan menyimpan informasi. Secara emosional, narasi yang dirancang
dengan baik mampu membangkitkan keterlibatan afektif dan motivasi intrinsik
(Mawasi et al., 2021). Efektivitas ini semakin diperkuat oleh kemampuan narasi
untuk mengkontekstualisasikan materi, menciptakan relevansi personal,
menyederhanakan konsep yang kompleks, serta memfasilitasi pembelajaran aktif
dan reflektif (Kim et al., 2021).


```
11
```
**2.2** **_Large Language Models_** **(LLM)**
_Large Language Models_ (LLM) merupakan model kecerdasan buatan
yang dirancang untuk memahami dan menghasilkan teks dalam bahasa manusia
secara alami dan fasih. Model ini dibangun menggunakan arsitektur _deep
learning_ , khususnya transformer, dengan jumlah parameter yang sangat besar,
bahkan mencapai miliaran hingga triliunan, serta dilatih pada data teks dalam
volume masif (Zhao et al., 2023). Fondasi utama LLM modern adalah arsitektur
_transformer_ , yang mengandalkan mekanisme _self-attention_ untuk menangkap
hubungan dan dependensi kata dalam satu urutan teks secara simultan, sehingga
mampu memahami konteks secara mendalam dan menghasilkan teks yang
koheren.
Dalam praktiknya, LLM telah menunjukkan kemampuan menghasilkan
berbagai bentuk narasi, mulai dari jawaban terbuka, rangkuman, hingga cerita
kreatif. Namun, penelitian mutakhir menunjukkan bahwa meskipun LLM mampu
menghasilkan teks naratif yang panjang dan beragam, model ini masih
menghadapi tantangan signifikan, seperti kecenderungan menghasilkan repetisi,
penurunan kualitas pada teks yang panjang, serta kesulitan menjaga konsistensi
dan kualitas narasi secara keseluruhan. Hal ini menjadi perhatian utama, terutama
untuk aplikasi yang membutuhkan narasi panjang dan konsistensi faktual, seperti
dalam edukasi atau penulisan ilmiah.

**2.3** **_Retrieval-Augmented Generation_** **(RAG)**
RAG adalah pendekatan yang mengintegrasikan LLM dengan modul
_retrieval_ eksternal. Sistem ini mengambil dokumen atau data relevan dari basis data
eksternal berdasarkan _query_ pengguna, lalu menggabungkannya ke dalam proses
generasi jawaban. Dengan demikian, RAG secara signifikan mengurangi halusinasi
karena jawaban didasarkan pada sumber data nyata, bukan hanya pengetahuan
internal model (Peng et al., 2024; Shuster et al., 2021). RAG terdiri dari dua
komponen utama: _retrieval_ untuk mengambil data relevan dan _generation_ untuk
menghasilkan respons berbasis data yang diambil (Guo et al., 2024). Namun, RAG
tradisional masih menghadapi tantangan seperti retrieval noise dan keterbatasan
dalam memahami hubungan antar entitas (Peng et al., 2024).


```
12
```
**2.4** **_Knowledge Graph_** **(KG)**
KG adalah struktur data terstruktur yang merepresentasikan entitas dan
hubungan antar entitas secara eksplisit. Integrasi KG ke dalam RAG mengatasi
kelemahan RAG tradisional, khususnya dalam memahami dan menavigasi relasi
kompleks antar entitas. KG memungkinkan sistem untuk melakukan reasoning
multi-hop, menjaga konteks, dan meningkatkan akurasi serta koherensi jawaban
(Peng et al., 2024). KG juga membantu dalam mengorganisasi dan mengindeks
pengetahuan sehingga retrieval menjadi lebih presisi dan kontekstual. Dengan KG,
sistem dapat menelusuri jalur relasi antar entitas, memperkaya konteks, dan
mengurangi informasi yang tidak relevan (Peng et al., 2024).

**2.5 LightRAG**
LightRAG adalah kerangka kerja spesifik yang mengintegrasikan KG ke
dalam proses RAG dengan cara yang efisien dan ringan. LightRAG menggunakan
_graph structure_ dalam proses _indexing_ dan _retrieval_ , memungkinkan _dual-level
retrieval_ (tingkat entitas dan relasi) untuk menghasilkan konteks yang lebih kaya
dan relevan. _Framework_ ini menggabungkan kecepatan _retrieval_ berbasis _vektor_
dengan pemahaman relasi dari KG, serta mendukung _incremental update_ agar
sistem tetap responsif terhadap data baru (Guo et al., 2024). LightRAG terbukti
meningkatkan akurasi, efisiensi, dan _faithfulness_ jawaban, serta mengurangi
fragmentasi informasi yang sering terjadi pada RAG konvensional (Guo et al.,
2024).

**2.6** **_Agentic_** **AI**
_Agentic_ AI didefinisikan sebagai sistem kecerdasan buatan yang otonom,
mampu melakukan perencanaan, penggunaan alat ( _tool use_ ), dan refleksi diri.
Sistem ini tidak hanya menjalankan instruksi secara pasif, tetapi juga secara proaktif
mengidentifikasi tujuan, merancang langkah-langkah pencapaian, memilih serta
mengoperasikan alat yang relevan, dan melakukan evaluasi serta perbaikan mandiri
terhadap proses yang dijalankan (Liu et al., 2024). Dalam konteks generasi cerita,
agentic AI mampu membagi proses menjadi beberapa sub-tugas, merencanakan
alur narasi, menggunakan berbagai sumber pengetahuan, dan secara iteratif
merevisi hasil untuk memastikan koherensi dan relevansi cerita. Kemampuan


```
13
```
perencanaan memungkinkan agentic AI untuk mengorkestrasi urutan peristiwa
dalam cerita, menjaga kesinambungan logika, dan menghindari inkoherensi naratif
yang sering muncul pada model generatif konvensional (Liu et al., 2024).
Penggunaan alat ( _tool use_ ) memperluas kapabilitas agentic AI, misalnya dengan
mengakses basis data eksternal, melakukan _retrieval_ informasi, atau
mengintegrasikan modul penalaran berbasis pengetahuan terstruktur. Sementara
itu, _self-reflection_ memungkinkan _agentic_ AI untuk menilai dan memperbaiki hasil
generasi cerita secara mandiri, baik melalui evaluasi internal maupun umpan balik
pengguna, sehingga kualitas narasi dapat terus ditingkatkan (Liu et al., 2024).
Paradigma agentic AI ini sangat relevan untuk pembuatan _story-based
learning_ , di mana proses pembelajaran berbasis cerita menuntut narasi yang
koheren, kontekstual, dan adaptif terhadap kebutuhan pembelajar. Dalam
implementasinya, _agentic_ AI dapat mengorkestrasi seluruh proses pembuatan cerita
mulai dari perencanaan plot, pemilihan karakter, hingga revisi narasi berdasarkan
refleksi dan umpan balik. Dengan demikian, agentic AI berperan sebagai penggerak
utama dalam story-based learning, memastikan setiap tahapan pembuatan cerita
berjalan terstruktur, adaptif, dan mampu mengatasi masalah inkoherensi naratif,
sehingga pengalaman belajar menjadi lebih mendalam dan bermakna (Liu et al.,
2024).

**2.7 Halusinasi dan** **_Faithfulness_**
Halusinasi pada LLM adalah fenomena generasi informasi yang tampak
meyakinkan, namun secara faktual tidak selaras dengan data sumber ( _fact-
conflicting hallucination_ ) (Lin et al., 2024; Zhang et al., 2023). Untuk mengatasi
masalah halusinasi faktual tersebut, penelitian ini mengukur kinerja _faithfulness_
(kesetiaan faktual). Secara operasional, _faithfulness_ didefinisikan sebagai tingkat
kepatuhan generasi teks terhadap fakta dalam basis pengetahuan acuan
( _knowledge graph_ ). Output dianggap _faithful_ jika selaras dengan sumber, tanpa
distorsi atau fabrikasi faktual (Lin et al., 2024; Zhang et al., 2023).

**2.8 Inkoherensi Naratif dan Koherensi Naratif**
Inkoherensi naratif adalah kegagalan model dalam menjaga konsistensi
internal sebuah cerita. Hal ini bermanifestasi sebagai diskontinuitas alur ( _plot_


```
14
```
_holes_ ), perubahan karakter yang tidak logis, atau pelanggaran aturan dunia cerita,
yang sering terjadi pada narasi panjang (Ji et al., 2022; Zhang et al., 2023). Untuk
mengevaluasi masalah tersebut, penelitian ini mengukur koherensi naratif. Metrik
ini secara operasional didefinisikan sebagai kualitas konsistensi logis dari sebuah
cerita, yang menilai kemampuan sistem mempertahankan alur terstruktur serta
konsistensi karakter dan plot (Ji et al., 2022; Zhang et al., 2023).

**2.9** **_State-of-The-Art_**
Dalam penelitian ini yang berjudul "Analisis Kinerja Koherensi Naratif
Dan _Faithfulness_ Pada Sistem _Agentic_ Al Dan LightRAG Untuk Pembelajaran
Berbasis Cerita", penting untuk memahami konteks dan perkembangan terkini.
Secara lebih spesifik pada evaluasi, Subbiah et al. (2024) membangun
dataset baru bernama StorySumm. Dataset ini terdiri dari ringkasan cerita pendek
yang dihasilkan oleh LLM (seperti GPT-4, Claude-2.1, Llama-2-70B), yang
kemudian diberi label _faithfulness_ secara lokal (per bagian) beserta penjelasan
kesalahannya. Penilaian dilakukan oleh annotator manusia, termasuk penulis cerita
asli, untuk menguji metode evaluasi otomatis dan manual dalam mendeteksi
ketidaksetiaan ringkasan terhadap sumbernya.
Dari perspektif kreativitas, Doshi & Hauser (2023) menggunakan data dari
293 cerita hasil eksperimen daring. Dalam eksperimen tersebut, partisipan manusia
menulis cerita dengan atau tanpa bantuan ide dari AI generatif. Cerita-cerita ini
kemudian dievaluasi oleh penilai manusia untuk aspek kreativitas, kualitas, dan
keberagaman tematik, guna menganalisis dampak akses ide AI terhadap kualitas
dan variasi cerita yang dihasilkan manusia.
Dalam konteks pendidikan, Pellas (2023) mengumpulkan data dari tugas
pembuatan cerita mahasiswa yang dibagi menjadi dua kelompok: satu
menggunakan platform AI generatif (seperti Sudowrite, Jasper, Shortly AI) dan satu
lagi menggunakan platform konvensional (seperti Storybird, Storyjumper). Data
yang dikumpulkan mencakup hasil karya tulis, serta skor _narrative intelligence_ ,
_writing self-efficacy_ , dan identitas kreatif sebelum dan sesudah intervensi. Data ini
digunakan untuk mengukur perubahan kemampuan naratif dan kepercayaan diri
menulis setelah menggunakan AI generatif.
Meninjau dari sisi arsitektur, Wang et al. (2022) menyajikan survei


```
15
```
komprehensif yang tidak mengumpulkan data primer, melainkan merangkum dan
menganalisis berbagai dataset cerita yang telah ada (seperti TVRecap, LiSCU, dan
STORAL). Studi ini menganalisis karakteristik dataset, struktur _knowledge graph_ ,
dan metrik evaluasi yang digunakan dalam riset _story generation_. Tinjauan ini
menekankan pentingnya integrasi _knowledge graph_ untuk meningkatkan koherensi
global dan _grounding_ cerita, yang secara langsung berkaitan dengan analisis
arsitektur LightRAG pada penelitian ini.
Meski demikian, sebagian besar penelitian seperti Subbiah (2024) dan
Pellas (2023) masih terbatas pada evaluasi kinerja LLM umum dalam tugas naratif
atau mengukur dampak platform AI secara holistik. Sementara itu, studi arsitektur
seperti Wang et al. (2022) cenderung bersifat survei teoretis tanpa analisis kinerja
empiris pada sistem hibrida spesifik. Hal ini menunjukkan adanya celah penelitian
yang penting, yaitu analisis kuantitatif yang secara spesifik mengukur kinerja
arsitektur _agentic_ AI dan LightRAG dalam menghasilkan cerita pembelajaran.
Secara khusus, penelitian ini berfokus pada dua metrik fundamental yang masih
kurang dieksplorasi secara bersamaan pada sistem tersebut: Koherensi Naratif
untuk konsistensi alur dan Faithfulness untuk akurasi faktual terhadap _knowledge
graph_. Dengan mengisi celah tersebut, penelitian ini diharapkan dapat memberikan
kontribusi akademis berupa wawasan empiris mengenai efektivitas sistem hibrida
ini, sekaligus kontribusi praktis sebagai landasan pengembangan alat bantu
pembelajaran berbasis cerita yang lebih andal, koheren, dan faktual.

```
Tabel 1.1 State-of-the-Art
Penulis Tahun Data Metode/Mo
del AI
```
```
Variabel
Evaluasi
```
```
Sitasi
```
```
Subbiah
et al.
```
```
2024 Cerita
pendek
orisinal
(StorySum
m)
```
### GPT-4,

```
Claude-2.1,
Llama-2-
70B
```
```
Faithfulness
, koherensi,
subteks
```
```
(Subbi
ah et
al.,
2024)
```

```
16
```
Doshi &
Hauser

```
2023 293 cerita
eksperime
n online
```
```
LLM Kreativitas,
kenikmatan,
keberagama
n
```
```
(Doshi
&
Hauser
, 2023)
```
Pellas 2023 Tugas
pembuatan
cerita
mahasiswa

```
Sudowrite,
Jasper,
Shortly AI
```
```
Narrative
intelligence,
self-efficacy
```
```
(Pellas,
2023)
```
Wang et
al.

```
2022 Korpus
cerita &
knowledge
graph
```
```
Structured
knowledge-
enhanced
```
```
Koherensi
global,
grounding
```
```
(Wang
et al.,
2022)
```

```
17
```
### BAB 3

### METODOLOGI

**3.1 Desain Penelitian**
Penelitian ini mengadopsi pendekatan _Design Research Methodology_
(DRM), sebuah kerangka kerja yang dirintis oleh Blessing dan Chakrabarti. DRM
menawarkan alur kerja yang sistematis, dirancang untuk meningkatkan mutu riset
desain melalui tahapan yang terstruktur, efisien, dan efektif (Blessing, 2009).
Metodologi ini dinilai sangat relevan untuk riset yang berpusat pada perancangan,
pengembangan, dan evaluasi sebuah sistem berbasis kecerdasan buatan, khususnya
dalam konteks analisis kinerja sistem _Agentic_ AI dan LightRAG untuk generasi
konten pembelajaran berbasis cerita. Kerangka kerja DRM sendiri tersusun atas
empat fase fundamental:

1. Klarifikasi Riset ( _Research Clarification_ ): Fase awal ini difokuskan untuk
    mengidentifikasi serta merumuskan masalah riset secara jernih, menetapkan
    sasaran yang hendak dicapai, dan mendefinisikan ruang lingkup penelitian.
    Pada tahap ini, dilakukan pengumpulan informasi fundamental untuk
    memantapkan arah dan fokus riset.
2. Studi Deskriptif I ( _Descriptive Study I_ ): Fase kedua ini bertujuan untuk
    menganalisis situasi aktual yang berkaitan dengan masalah riset.
    Implementasinya melibatkan kajian literatur yang mendalam serta
    pengumpulan data awal untuk memperoleh pemahaman komprehensif
    mengenai konteks dan fenomena yang diteliti.
3. Studi Preskriptif ( _Prescriptive Study_ ): Berlandaskan temuan dari fase
    sebelumnya, tahap ini berpusat pada perancangan dan pengembangan
    solusi. Peneliti merumuskan sebuah desain atau intervensi yang secara
    teoretis diharapkan mampu menjawab permasalahan yang telah
    diidentifikasi.
4. Studi Deskriptif II ( _Descriptive Study II_ ): Fase terakhir ini merupakan tahap
    evaluasi terhadap solusi yang telah dirancang. Pengujian dilakukan untuk
    mengumpulkan data empiris guna menilai efektivitas dan kinerja dari solusi
    tersebut. Hasil dari evaluasi ini dapat menjadi dasar untuk melakukan revisi
    atau penyempurnaan lebih lanjut.


```
18
```
# Gambar 3.1 DRM

Melalui penerapan DRM, penelitian ini diarahkan untuk menghasilkan
temuan yang tidak hanya bernilai akademis, tetapi juga memiliki signifikansi
praktis, sehingga memastikan bahwa hasil analisis dapat memberikan wawasan
yang aplikatif dalam konteks yang sesungguhnya.


```
19
```
**3.1.1** **_Research Clarification_**
Tahap ini berfungsi sebagai fondasi penelitian dengan tujuan utama untuk
mengidentifikasi dan memperjelas masalah, merumuskan tujuan, serta menetapkan
batasan yang tegas. Berdasarkan analisis latar belakang, masalah inti yang
diidentifikasi adalah adanya dua tantangan fundamental pada LLM saat digunakan
untuk generasi narasi pembelajaran skala panjang. Halusinasi yang mengancam
validitas faktual konten edukasi, dan inkoherensi naratif, yang merusak alur logika
dan konsistensi cerita. Meskipun arsitektur seperti LightRAG dan paradigma
_Agentic_ AI telah diusulkan sebagai solusi teoretis, tinjauan literatur menunjukkan
adanya kesenjangan riset yang signifikan, yaitu kurangnya analisis kinerja
kuantitatif yang mendalam untuk sistem hibrida ini pada domain kreatif. Untuk
mengisi kesenjangan tersebut, tujuan penelitian ini ditetapkan secara spesifik untuk
menganalisis dan mengukur kinerja sistem dari dua dimensi: Koherensi Naratif,
untuk menilai kemampuannya mengatasi inkoherensi, dan _faithfulness_ , untuk
mengukur kemampuannya mengatasi halusinasi dengan tetap setia pada basis
pengetahuan terstruktur ( _Knowledge Graph_ ). Ruang lingkup penelitian ini dibatasi
pada analisis arsitektur spesifik yang diusulkan, dengan evaluasi dilakukan secara
otomatis menggunakan pendekatan _LLM-as-a- judge_ dan tidak melibatkan
pengguna akhir atau perbandingan dengan arsitektur RAG lainnya.

**3.1.2** **_Descriptive Study I_**
Tahap kedua dalam metodologi penelitian ini, _Descriptive Study I_ , berfokus
pada analisis kondisi terkini yang relevan dengan permasalahan melalui studi
literatur yang mendalam untuk membangun landasan teoretis dan mengidentifikasi
kesenjangan riset ( _research gap_ ). Pelaksanaan tahap ini diwujudkan secara
komprehensif dalam Bab II Kajian Pustaka, di mana peneliti melakukan dua
aktivitas utama: menguraikan landasan konseptual dan meninjau penelitian-
penelitian terdahulu.
Pertama, peneliti melakukan kajian pustaka untuk membangun fondasi
teoretis yang kuat. Kajian ini secara sistematis menguraikan konsep-konsep inti
yang menjadi pilar penelitian, dimulai dari domain aplikasi yaitu Pembelajaran
Berbasis Cerita ( _Story-Based Learning_ ) untuk memahami prinsip pedagogisnya.
Selanjutnya, peneliti mendalami teknologi yang digunakan, yaitu _Large Language_


```
20
```
_Models_ (LLM), serta tantangan fundamental yang menyertainya, yakni halusinasi
dan inkoherensi naratif. Sebagai solusi atas tantangan tersebut, peneliti mengkaji
arsitektur teknis yang relevan, mencakup _Retrieval-Augmented Generation_ (RAG),
_Knowledge Graph_ (KG), kerangka kerja LightRAG, dan paradigma Agentic AI.
Terakhir, definisi operasional untuk metrik evaluasi, yaitu Koherensi Naratif dan
_Faithfulness_ , ditetapkan berdasarkan literatur untuk memastikan pengukuran yang
valid.
Kedua, peneliti melakukan tinjauan terhadap penelitian-penelitian terdahulu
( _state-of-the-art_ ) untuk memetakan lanskap riset terkini dan memposisikan
penelitian ini di dalamnya. Analisis ini menunjukkan bahwa sebagian besar
penelitian yang ada masih terbatas pada evaluasi kinerja LLM secara umum,
mengukur dampak platform AI secara holistik, atau cenderung bersifat survei
teoretis tanpa analisis kinerja empiris pada sistem hibrida yang spesifik.
Berdasarkan tinjauan tersebut, peneliti berhasil mengidentifikasi sebuah
kesenjangan riset yang jelas: kurangnya analisis kuantitatif yang secara spesifik
mengukur kinerja arsitektur _Agentic AI_ dan _LightRAG_ dalam menghasilkan cerita
pembelajaran, khususnya pada dua metrik fundamental yaitu, Koherensi Naratif
dan _Faithfulness_ secara bersamaan. Dengan demikian, tahap _Descriptive Study I_ ini
berhasil menyediakan landasan teoretis yang kokoh sekaligus memvalidasi
kebaruan dan urgensi dari penelitian yang akan dilakukan.

**3.1.3** **_Prescriptive Study_**
Berlandaskan pemahaman yang diperoleh dari dua tahap sebelumnya,
_Prescriptive Study_ merupakan fase pengembangan solusi desain yang konkret, di
mana peneliti beralih dari landasan teoretis ke implementasi praktis. Pada tahap ini,
fokus utama adalah merancang dan mempersiapkan seluruh komponen yang
diperlukan untuk membangun dan menguji sistem generasi cerita. Proses ini terdiri
dari empat langkah utama yang saling berkaitan.
Pertama, peneliti melakukan perancangan arsitektur sistem. Langkah ini
melibatkan perancangan alur kerja interaksi antara komponen _Agentic AI_ sebagai
orkestrator naratif dan kerangka kerja LightRAG sebagai alat pencari fakta. Desain
ini memastikan bahwa agen dapat secara otonom merencanakan alur cerita,
memanggil _LightRAG_ untuk mendapatkan data faktual yang relevan, dan


```
21
```
merefleksikan outputnya untuk menjaga konsistensi.
Kedua, peneliti melakukan pembangunan basis pengetahuan. Sesuai dengan
ruang lingkup penelitian, sebuah _Knowledge Graph_ (KG) dibangun dari "korpus
cerita spesifik" yang telah ditentukan. Proses ini mencakup ekstraksi entitas dan
relasi dari teks sumber untuk menciptakan sebuah basis data terstruktur yang akan
berfungsi sebagai satu-satunya "sumber kebenaran" ( _single source of truth_ ) bagi
sistem untuk memastikan _faithfulness_ dari cerita yang dihasilkan.
Ketiga, peneliti mempersiapkan pembuatan set data evaluasi. Untuk
menguji kinerja sistem secara objektif, serangkaian skenario pengujian atau _prompt_
cerita dirancang. _Prompt_ ini dibuat secara representatif untuk memicu sistem
menghasilkan narasi yang dapat dianalisis, mencakup berbagai situasi yang
memungkinkan peneliti mengukur kemampuan sistem dalam menjaga koherensi
dan kesetiaan pada fakta.
Keempat, peneliti melakukan pengembangan instrumen evaluasi. Karena
evaluasi akan dilakukan secara otomatis, peneliti merancang rubrik penilaian
kuantitatif yang terstruktur untuk metrik koherensi naratif dan _faithfulness_.
Instrumen ini berupa serangkaian _prompt_ dan kriteria penilaian yang akan diberikan
kepada model evaluator ( _LLM-as-a- judge_ ) berupa gemini 2.5 pro pada tahap
pengujian selanjutnya, sehingga memastikan proses penilaian yang konsisten dan
terukur.

**3.1.4** **_Descriptive Study II_**
Tahap terakhir, _Descriptive Study II_ , adalah fase evaluasi empiris di mana
solusi yang telah dirancang pada _Prescriptive Study_ diuji untuk menilai
efektivitasnya secara kuantitatif. Tahap ini merupakan puncak dari proses
penelitian, di mana kinerja sistem diukur secara objektif untuk menjawab rumusan
masalah. Proses ini diawali dengan tahap generasi data, di mana sistem AI yang
telah dibangun dijalankan menggunakan set data evaluasi yang telah disiapkan
untuk menghasilkan sampel konten pembelajaran berbasis cerita. Output dari tahap
ini adalah sebuah korpus narasi yang akan menjadi objek analisis utama.
Selanjutnya, dilakukan pengumpulan data kinerja melalui evaluasi otomatis,
sesuai dengan ruang lingkup penelitian yang telah ditetapkan. Untuk metrik
koherensi naratif, instrumen _LLM-as-a- judge_ menerapkan rubrik penilaian yang


```
22
```
telah dirancang untuk memberikan skor kuantitatif pada setiap cerita secara holistik,
menilai konsistensi alur, karakter, dan logika narasi. Sementara itu, untuk metrik
_Faithfulness_ , dilakukan verifikasi otomatis dengan membandingkan setiap klaim
faktual dalam narasi yang dihasilkan terhadap triplet data yang ada di dalam
_Knowledge Graph_ untuk menghitung skor kesesuaian.
Data kuantitatif yang terkumpul dari kedua metrik tersebut kemudian
memasuki tahap analisis data. Pada tahap ini, peneliti menerapkan statistik
deskriptif untuk mengolah data, menghitung nilai-nilai seperti rata-rata, median,
dan standar deviasi dari skor kinerja sistem. Hasil analisis statistik ini akan disajikan
secara mendalam pada Bab IV Hasil dan Pembahasan, yang akan digunakan secara
langsung untuk menginterpretasikan temuan dan menjawab rumusan masalah
penelitian, sehingga melengkapi siklus _Design Research Methodology_ ini secara
utuh.

**3.2 Populasi dan Sampel**
Populasi dalam penelitian ini didefinisikan sebagai keseluruhan
kemungkinan cerita pembelajaran ( _universe of narrative outputs_ ) yang dapat
dihasilkan oleh sistem _agentic_ AI dan LightRAG. Batasan populasi ini secara
inheren ditentukan oleh totalitas pengetahuan yang terkandung dalam KG sumber,
yang dibangun dari "korpus cerita spesifik". Dengan kata lain, populasi mencakup
setiap variasi narasi yang secara teoretis dapat digenerasi oleh sistem berdasarkan
kombinasi entitas dan relasi yang ada.
Sampel penelitian adalah himpunan bagian representatif dari populasi yang
akan dianalisis secara langsung untuk mengukur kinerja sistem. Sampel yang
digunakan dalam penelitian ini adalah dataset HANNA, yang merupakan dataset
cerita hasil generasi model bahasa besar yang telah dilengkapi dengan penilaian
manusia untuk berbagai aspek kualitas cerita.
Set data evaluasi ini terdiri dari sejumlah cerita yang secara konkret
dihasilkan oleh sistem sebagai respons terhadap serangkaian skenario atau _prompt_
yang telah disiapkan sebelumnya. Teknik pengambilan sampel yang digunakan
adalah _purposive sampling_ , di mana setiap _prompt_ dalam set data evaluasi HANNA
dirancang secara sengaja untuk menguji berbagai aspek naratif dan relasi entitas
dalam KG. Hal ini memastikan bahwa sampel cerita yang dihasilkan representatif


```
23
```
untuk tujuan evaluasi kinerja koherensi naratif dan _faithfulness_.

**3.3 Instrumen Penelitian**
Bagian ini menguraikan instrumen penelitian yang digunakan untuk
mengevaluasi sistem generasi naratif berbasis _Retrieval-Augmented Generation_
(RAG). Instrumen utama yang dipilih adalah kerangka kerja SCORE ( _Story
Coherence and Retrieval Enhancement_ ) dan RAGAS ( _Retrieval-Augmented
Generation Assessment_ ). Pemilihan kedua kerangka kerja ini didasarkan pada
kemampuan mereka untuk menyediakan evaluasi yang mendalam dan terstruktur,
melampaui metrik tradisional, dengan fokus spesifik pada koherensi naratif dan
efektivitas komponen RAG. Selain itu, bagian ini akan merinci bagaimana
paradigma _LLM-as-a- Judge_ menjadi mekanisme fundamental yang mendasari
kedua instrumen tersebut.

**3.3.1** **_Story Coherence and Retrieval Enhancement_** **(SCORE)**
SCORE ( _Story Coherence and Retrieval Enhancement_ ) adalah sebuah
kerangka kerja yang dirancang khusus untuk mendeteksi dan mengatasi
inkonsistensi dalam narasi yang dihasilkan oleh AI. Arsitekturnya berfokus pada
tiga pilar koherensi naratif: konsistensi karakter, koherensi emosional, dan
pelacakan logis elemen plot (Yi et al., 2025). Secara unik, SCORE sendiri
mengimplementasikan pendekatan RAG untuk mengevaluasi output dari model
generatif lain, menjadikannya contoh sistem AI yang digunakan untuk
menganalisis sistem AI lainnya. Kerangka kerja SCORE terdiri dari tiga komponen
utama yang bekerja secara sinergis untuk memastikan koherensi narasi.

1. Pelacakan Status Dinamis ( _Dynamic State Tracking_ ): Komponen ini
    berfungsi sebagai penjaga kontinuitas naratif dengan memantau keadaan
    elemen-elemen kunci menggunakan logika simbolik. Untuk setiap item
    penting pada waktu (episode), sebuah status diskrit ditetapkan. Komponen
    ini mendeteksi "kesalahan kontinuitas" dengan menerapkan aturan logis
    formal. Sebuah kesalahan ditandai jika sebuah item yang sebelumnya
    berada dalam keadaan lost atau destroyed pada waktu tiba-tiba muncul
    kembali dalam keadaan active pada waktu tanpa adanya penjelasan naratif
    yang memadai. Jika terjadi pelanggaran, sistem akan melakukan koreksi


```
24
```
```
dengan mempertahankan keadaan sebelumnya.
```
2. Peringkasan Sadar-Konteks ( _Context-Aware Summarization_ ): Untuk
    melacak perkembangan plot secara efisien, SCORE menggunakan LLM
    untuk secara otomatis menghasilkan ringkasan dari setiap episode naratif.
    Ringkasan ini menangkap elemen-elemen esensial, termasuk poin-poin plot
    utama, tindakan karakter, interaksi signifikan dengan item kunci, dan
    perubahan nada emosional. Ringkasan-ringkasan ini kemudian disusun
    secara hierarkis, menciptakan jejak temporal dari narasi yang
    memungkinkan pelacakan perkembangan cerita dari waktu ke waktu.
3. Pengambilan Hibrida ( _Hybrid Retrieval_ ): Komponen ini adalah inti dari
    mekanisme RAG internal SCORE. Ringkasan episode yang telah dibuat
    disematkan ke dalam ruang vektor berdimensi tinggi, yang memungkinkan
    pencarian kesamaan semantik. Ketika menganalisis episode baru, sistem
    menggunakan metrik kesamaan kosinus untuk mengambil episode-episode
    masa lalu yang paling relevan secara semantik. Episode-episode dengan
    skor kesamaan tertinggi ini kemudian digunakan sebagai konteks untuk
    mengevaluasi konsistensi. Untuk meningkatkan ketahanan, pendekatan ini
    dilengkapi dengan lapisan pengambilan kedua yang menggunakan TF-IDF
    ( _Term Frequency-Inverse Document Frequency_ ) untuk pencarian berbasis
    kata kunci (leksikal), menciptakan strategi pengambilan hibrida. Selain itu,
    analisis sentimen diintegrasikan sebagai mekanisme penyaringan untuk
    memastikan konsistensi emosional antara episode saat ini dan konteks yang
    diambil.
    Formulasi yang digunakan dalam SCORE mencakup aturan logika dan
perhitungan matematis untuk memastikan evaluasi yang sistematis.
- Aturan Kesalahan Kontinuitas: Aturan ini secara formal mendefinisikan
kondisi untuk menandai pelanggaran kontinuitas status item.
IF (𝑆𝑆𝑖𝑖(𝑡𝑡𝑘𝑘−1)∈{lost, destroyed}) AND (𝑆𝑆𝑖𝑖(𝑡𝑡𝑘𝑘)=active) THEN ContinuityError
=TRUE
- Rumus Kesamaan Kosinus: di mana 𝑆𝑆�𝑒𝑒𝑐𝑐,𝑒𝑒𝑝𝑝� adalah skor kesamaan antara
vektor episode saat ini (𝑣𝑣𝑒𝑒𝑐𝑐) dan vektor episode masa lalu (𝑣𝑣𝑒𝑒𝑝𝑝).


```
25
```
### 𝑆𝑆�𝑒𝑒𝑐𝑐,𝑒𝑒𝑝𝑝�=

### 𝑣𝑣𝑒𝑒𝑐𝑐⋅𝑣𝑣𝑒𝑒𝑝𝑝

### |𝑣𝑣𝑒𝑒𝑐𝑐|⋅|𝑣𝑣𝑒𝑒𝑝𝑝|^

**3.3.2** **_Retrieval-Augmented Generation Assessment_** **(RAGAS)**
RAGAS ( _Retrieval-Augmented Generation Assessment_ ) adalah kerangka
kerja yang dirancang khusus untuk evaluasi pipa RAG secara objektif dan
kuantitatif. Filosofi inti di balik RAGAS adalah evaluasi komponensial, yang
memisahkan penilaian kinerja komponen _retriever_ dan _generator_. Pendekatan ini
memungkinkan identifikasi dan diagnosis masalah yang lebih tepat dalam alur kerja
RAG. Salah satu keunggulan utama RAGAS adalah kemampuannya untuk
menyediakan serangkaian metrik evaluasi yang tidak memerlukan anotasi manusia
sebagai _ground truth_ , sehingga membuatnya skalabel. RAGAS menawarkan
berbagai metrik, namun dua metrik yang paling fundamental untuk mengevaluasi
aspek inti dari sistem RAG adalah _faithfulness_ dan _context recall_.

- _Faithfulness:_ Metrik ini mengukur sejauh mana jawaban yang dihasilkan
    oleh model secara faktual konsisten dengan konteks yang telah diambil.
    Metrik ini secara efektif mengukur tingkat halusinasi pada output generator.
    Skor _Faithfulness_ berkisar dari 0 hingga 1, di mana skor yang lebih tinggi
    menunjukkan tingkat kesetiaan yang lebih baik terhadap sumber informasi.

```
Faithfulness Score=Jumlah klaim yang didukung oleh konteksTotal jumlah klaim dalam jawaban
```
- _Context Recall (Daya Panggil Konteks):_ Metrik ini mengevaluasi kinerja
    komponen _retriever_ dengan mengukur sejauh mana konteks yang diambil
    berhasil mencakup semua informasi relevan yang diperlukan untuk
    memberikan jawaban yang lengkap dan akurat. Untuk melakukan ini,
    _Context Recall_ menggunakan jawaban _ground truth_ atau referensi sebagai
    proksi untuk informasi ideal yang seharusnya diambil. Skor yang tinggi
    menunjukkan bahwa _retriever_ berhasil memanggil sebagian besar informasi
    penting dan tidak melewatkan detail krusial.

```
Context Recall=Jumlah klaim dalam referensi yang didukung oleh konteksTotal jumlah klaim dalam referensi
```
**3.4 Prosedur Penelitian**
Prosedur penelitian ini dimulai dengan tahap perancangan sistem, yang


```
26
```
melibatkan pengembangan arsitektur sistem _agentic_ AI dan LightRAG. Tahap ini
mencakup perencanaan interaksi antara komponen-komponen sistem untuk
menghasilkan narasi pembelajaran yang koheren dan akurat. Setelah arsitektur
sistem selesai, peneliti membangun basis pengetahuan yang terdiri dari KG, yang
menjadi sumber utama untuk memastikan akurasi fakta dalam cerita yang
dihasilkan.
Setelah itu, peneliti mempersiapkan set data evaluasi yang terdiri dari
prompt cerita yang dirancang untuk menguji kinerja sistem pada dua metrik utama:
Koherensi Naratif dan Faithfulness. Skenario pengujian dibuat untuk mencakup
berbagai situasi yang menilai kemampuan sistem dalam menjaga konsistensi dan
kesetiaan pada fakta. Seluruh proses ini kemudian diikuti dengan pengembangan
instrumen evaluasi yang akan mengukur kinerja sistem secara objektif dan
konsisten menggunakan LLM sebagai model evaluator.
Pada tahap evaluasi empiris, sistem yang telah dibangun diuji dengan
menggunakan set data yang telah dipersiapkan sebelumnya. Evaluasi dilakukan
dengan memanfaatkan instrumen yang telah dirancang untuk mengukur kinerja
sistem berdasarkan kriteria yang telah ditetapkan. Semua langkah ini diikuti dengan
pengumpulan data yang dilakukan dengan metode evaluasi otomatis untuk
mengukur koherensi naratif dan _faithfulness_.

**3.5 Analisis Data**
Analisis data dalam penelitian ini akan menggunakan pendekatan
kuantitatif dengan fokus pada statistik deskriptif untuk menjawab rumusan masalah
mengenai kinerja koherensi naratif dan _faithfulness_. Proses analisis akan dilakukan
menggunakan lingkungan komputasi Python dengan pustaka ilmiah seperti pandas
untuk manipulasi data dan matplotlib serta seaborn untuk visualisasi. Langkah-
langkah analisis data adalah sebagai berikut:

1. Pengumpulan Skor Kinerja: Data kuantitatif akan dikumpulkan dari hasil
    evaluasi menggunakan instrumen SCORE (untuk koherensi naratif) dan
    RAGAS (untuk _faithfulness_ ). Setiap narasi yang dihasilkan oleh sistem akan
    memiliki skor numerik untuk kedua metrik ini.
2. Analisis Statistik Deskriptif: Untuk menjawab masing-masing rumusan
    masalah, akan dihitung statistik deskriptif berikut:


```
27
```
```
o Ukuran Tendensi Sentral (Mean, Median): Rata-rata ( mean ) dan
nilai tengah ( median ) dari skor koherensi dan faithfulness akan
dihitung. Ukuran ini akan memberikan gambaran umum atau
"kinerja tipikal" dari sistem pada kedua dimensi tersebut. Ini secara
langsung menjawab pertanyaan "bagaimana kinerja" sistem.
o Ukuran Dispersi (Standar Deviasi): Standar deviasi dari skor akan
dihitung untuk memahami tingkat konsistensi kinerja sistem.
Standar deviasi yang rendah menunjukkan bahwa sistem berkinerja
secara konsisten, sedangkan standar deviasi yang tinggi
menunjukkan adanya variabilitas yang besar pada kualitas output.
```
3. Visualisasi Data: Hasil dari statistik deskriptif akan disajikan secara visual
    melalui histogram atau _box plot_. Visualisasi ini bertujuan untuk
    menunjukkan distribusi skor kinerja, mengidentifikasi adanya pencilan
    ( _outliers_ ), dan memberikan pemahaman yang lebih intuitif mengenai
    sebaran kinerja sistem untuk koherensi dan _faithfulness_.
4. Interpretasi Hasil: Pemaknaan temuan akan berfokus pada deskripsi
    kuantitatif dari kinerja sistem. Misalnya, skor rata-rata _faithfulness_ yang
    tinggi (misalnya, >0.9) akan diinterpretasikan sebagai kemampuan sistem
    yang sangat baik dalam menghindari halusinasi. Sebaliknya, skor koherensi
    naratif dengan standar deviasi yang tinggi akan diinterpretasikan bahwa
    sistem belum konsisten dalam menjaga alur cerita.


```
28
```
### DAFTAR PUSTAKA

Ammanabrolu, P., Cheung, W., Broniec, W., & Riedl, M. (2021). Automated
Storytelling via Causal, Commonsense Plot Ordering. _Proceedings of the Aaai
Conference on Artificial Intelligence_.
https://doi.org/10.1609/aaai.v35i7.16733
Doshi, A., & Hauser, O. (2023). Generative AI enhances individual creativity but
reduces the collective diversity of novel content. _Science Advances_ , _10_.
https://doi.org/10.1126/sciadv.adn5290
Guo, Z., Xia, L., Yu, Y., Ao, T., & Huang, C. (2024). _LightRAG: Simple and fast
retrieval-Augmented Generation_.
Hosseini, S., & Seilani, H. (2025). The role of agentic AI in shaping a smart future:
A systematic review. _Array (N. Y.)_ , _26_ (100399), 100399.
Ji, S., Pan, S., Cambria, E., Marttinen, P., & Yu, P. S. (2022). A Survey on
Knowledge Graphs: Representation, Acquisition, and Applications. _Ieee
Transactions on Neural Networks and Learning Systems_.
https://doi.org/10.1109/tnnls.2021.3070843
Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., Ishii, E., Bang, Y., Chen, D., Dai,
W., Madotto, A., & Fung, P. (2022). Survey of Hallucination in Natural
Language Generation. _ACM Computing Surveys_ , _55_ , 1–38.
https://doi.org/10.1145/3571730
Kim, D., Coenraad, M., & Park, H. R. (2021). Digital Storytelling as a Tool for
Reflection in Virtual Reality Projects. _Journal Of Curriculum
Studies Research_. https://doi.org/10.46303/jcsr.2021.9
Lin, Z., Guan, S., Zhang, W., Zhang, H., Li, Y., & Zhang, H. (2024). Towards
trustworthy LLMs: a review on debiasing and dehallucinating in large
language models. _Artif. Intell. Rev._ , _57_ , 243. https://doi.org/10.1007/s10462-
024-10896-y
Liu, Y., Lo, S. K., Lu, Q., Zhu, L., Zhao, D., Xu, X., Harrer, S., & Whittle, J. (2024).
Agent Design Pattern Catalogue: A Collection of Architectural Patterns for
Foundation Model based Agents. _ArXiv_ , _abs/2405.10467_.
https://doi.org/10.48550/arxiv.2405.10467
Mawasi, A., Nagy, P., Finn, E., & Wylie, R. (2021). Narrative-Based Learning


```
29
```
Activities for Science Ethics Education: An Affordance Perspective. _Journal
of Science Education and Technology_. https://doi.org/10.1007/s10956-021-
09928-x
Pellas, N. (2023). The Effects of Generative AI Platforms on Undergraduates’
Narrative Intelligence and Writing Self-Efficacy. _Education Sciences_.
https://doi.org/10.3390/educsci13111155
Peng, B., Zhu, Y., Liu, Y., Bo, X., Shi, H., Hong, C., Zhang, Y., & Tang, S. (2024).
Graph Retrieval-Augmented Generation: A Survey. _ArXiv_ , _abs/2408.08921_.
https://doi.org/10.48550/arxiv.2408.08921
Shuster, K., Poff, S., Chen, M., Kiela, D., & Weston, J. (2021). _Retrieval
Augmentation Reduces Hallucination in Conversation_. 3784–3803.
https://doi.org/10.18653/v1/2021.findings-emnlp.320
Su, J., Dai, Q., Guérin, F., & Zhou, M. (2021). BERT-hLSTMs: BERT and
Hierarchical LSTMs for Visual Storytelling. _Computer Speech & Language_.
https://doi.org/10.1016/j.csl.2020.101169
Subbiah, M., Zhang, S., Chilton, L., & McKeown, K. (2024). Reading Subtext:
Evaluating Large Language Models on Short Story Summarization with
Writers. _Transactions of the Association for Computational Linguistics_ , _12_ ,
1290–1310. https://doi.org/10.1162/tacl_a_00702
Wang, Y., Lin, J., Yu, Z., Hu, W., & Karlsson, B. (2022). Open-world Story
Generation with Structured Knowledge Enhancement: A Comprehensive
Survey. _Neurocomputing_ , _559_ , 126792.
https://doi.org/10.48550/arxiv.2212.04634
Yi, Q., He, Y., Wang, J., Song, X., Qian, S., Yuan, X., Xin, Y., Wang, Y., Tang, J.,
Li, Y., Lin, J., He Hongyang and Tian, Z., Xu, T., Li, K., Lu, K., Huo, M.,
Chen, J., Zhang, M., Shi, T., & Ni, J. (2025). SCORE: Story Coherence and
Retrieval Enhancement for AI Narratives. In _arXiv [cs.CL]_.
Zhang, Y., Li, Y., Cui, L., Cai, D., Liu, L., Fu, T., Huang, X., Zhao, E., Zhang, Y.,
Chen, Y., Wang, L., Luu, A., Bi, W., Shi, F., & Shi, S. (2023). Siren’s Song in
the AI Ocean: A Survey on Hallucination in Large Language Models. _ArXiv_ ,
_abs/2309.01219_. https://doi.org/10.48550/arxiv.2309.01219
Zhang, Y., Sun, S., Gao, X., Fang, Y., Brockett, C., Galley, M., Gao, J., & Dolan,


```
30
```
B. (2022). RetGen: A Joint Framework for Retrieval and Grounded Text
Generation Modeling. _Proceedings of the Aaai Conference on Artificial
Intelligence_. https://doi.org/10.1609/aaai.v36i10.21429
Zhao, W. X., Zhou, K., Li, J., Tang, T., Wang, X., Hou, Y., Min, Y., Zhang, B.,
Zhang, J., Dong, Z., Du, Y., Yang, C., Chen, Y., Chen, Z., Jiang, J., Ren, R.,
Li, Y., Tang, X., Liu, Z., ... Wen, J.-R. (2023). A Survey of Large Language
Models. _ArXiv_ , _abs/2303.18223_. https://doi.org/10.48550/arxiv.2303.18223


