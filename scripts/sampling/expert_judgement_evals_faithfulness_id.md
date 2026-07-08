# Evaluasi Sampel Cerita (Sistem Bahasa Indonesia - FAITHFULNESS - 5 Cerita)
Metode: **Disproportional Stratified Sampling** dengan **Hierarchical Metrik: Rata-rata Faithfulness (FABLES & RAGAS setara) > G-Eval Koherensi**.

## Evaluasi Sampel 1: SKOR TINGGI (Best Cases)
### Judul: Misteri GPT-4: Petualangan Pengetahuan Leo dan Mia

- **Koherensi (G-Eval Norm):** `0.980`
- **Faithfulness (RAGAS):** `1.000`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness (RAGAS + FABLES) Max. Jika sama, dipilih Koherensi tertinggi.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** GPT-4 secara resmi dirilis oleh OpenAI pada tanggal 14 Maret 2023.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** GPT-4 memiliki pemahaman bahasa yang jauh lebih baik dan kemampuan penalaran yang canggih.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** GPT-4 memiliki kreativitas yang luar biasa.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** GPT-4 dapat membantu pengguna menulis cerita, membuat lagu, atau menghasilkan ide-ide baru.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** GPT-4 dapat menerima input multimodal, seperti gambar.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** GPT-4 dapat 'melihat' gambar bahan makanan dan menyarankan resep masakan.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**7. Klaim:** GPT-4 dapat menjadi alat yang sangat membantu dalam berbagai bidang, dari pendidikan, seni, hingga membantu membuat proyek kreatif.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**8. Klaim:** GPT-4 terus belajar dari setiap percakapan.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 2: SKOR TINGGI (Best Cases)
### Judul: Misteri Brigade Tank Tatsin: Penemuan Alex

- **Koherensi (G-Eval Norm):** `0.960`
- **Faithfulness (RAGAS):** `1.000`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness (RAGAS + FABLES) Max. Jika sama, dipilih Koherensi tertinggi.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Tank pertama, Mark I, digunakan pada tahun 1916 dalam Pertempuran Somme.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Little Willie adalah prototipe pertama tank, dibuat pada tahun 1915.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Tank adalah kendaraan lapis baja yang diciptakan untuk membantu tentara melewati parit dan melindungi mereka dari tembakan senapan mesin.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** Informasi militer yang sangat spesifik jarang ada di buku-buku umum.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** Informasi militer yang sangat spesifik biasanya tersimpan dalam arsip khusus, seringkali digital.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** 5th Separate Guards Tatsin Red Banner Order of Suvorov Tank Brigade dibentuk pada 16 Februari 1943.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**7. Klaim:** Nomor unit militer 5th Separate Guards Tatsin Red Banner Order of Suvorov Tank Brigade adalah Unit Militer Lapangan 41655 (Polevoy Pochty 41655).
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**8. Klaim:** Tank, sejak pertama kali digunakan pada tahun 1916, telah berevolusi dan menjadi bagian integral dari banyak unit militer.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 3: SKOR SEDANG (Average Cases)
### Judul: Misteri Liga Super Wanita Turki

- **Koherensi (G-Eval Norm):** `0.900`
- **Faithfulness (RAGAS):** `1.000`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** Jarak 3D terdekat dengan Median Sistem: Koherensi (0.880), RAGAS (1.000), dan FABLES (1.000).

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Liga Super Sepak Bola Wanita Turki saat ini diikuti oleh 16 tim.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Ke-16 tim di Liga Super Sepak Bola Wanita Turki dibagi menjadi dua grup, yaitu Grup A dan Grup B.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Masing-masing grup di Liga Super Sepak Bola Wanita Turki berisi 8 tim.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** Setiap tim di dalam grup Liga Super Sepak Bola Wanita Turki akan bertanding melawan tim lain dalam format dua putaran, yaitu pertandingan kandang dan tandang.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** Setelah semua pertandingan grup Liga Super Sepak Bola Wanita Turki selesai, tim teratas dari masing-masing grup, yaitu juara Grup A dan juara Grup B, akan melaju ke babak playoff.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Babak playoff Liga Super Sepak Bola Wanita Turki terdiri dari semifinal dan final untuk memperebutkan gelar juara.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 4: SKOR RENDAH (Worst Cases)
### Judul: Misteri Makam Alexander Stewart

- **Koherensi (G-Eval Norm):** `0.940`
- **Faithfulness (RAGAS):** `0.400`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness Min. Jika sama, dipilih Koherensi terendah.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Nama ‘Alexander Stewart’ adalah nama yang umum di Skotlandia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Alexander Stewart, Earl of Buchan, adalah salah satu putra Raja Robert II dari Skotlandia.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**3. Klaim:** Alexander Stewart, Earl of Buchan, dikenal karena reputasinya yang keras dan terkadang brutal.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**4. Klaim:** Alexander Stewart, Earl of Buchan, membakar Katedral Elgin pada tahun 1390.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**5. Klaim:** Alexander Stewart, alias ‘Wolf of Badenoch’, dimakamkan di Katedral Elgin, Skotlandia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Makam Alexander Stewart adalah salah satu makam yang paling menarik di Katedral Elgin.
- FABLES: `PARTIAL_SUPPORT`
- RAGAS : `PARTIAL_SUPPORT`

**7. Klaim:** Makam Alexander Stewart adalah makam batu yang dihiasi dengan patung dirinya dalam baju zirah.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**8. Klaim:** Katedral Elgin sebagian besar kini menjadi reruntuhan.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**9. Klaim:** Katedral Elgin dijuluki ‘Lentera Utara’ karena keindahannya di masa lalu.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**10. Klaim:** Makam Alexander Stewart terletak di bagian tengah Katedral Elgin.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

---

## Evaluasi Sampel 5: SKOR RENDAH (Worst Cases)
### Judul: Misteri Jalur Kereta Tua

- **Koherensi (G-Eval Norm):** `0.920`
- **Faithfulness (RAGAS):** `0.800`
- **Faithfulness (FABLES):** `0.800`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness Min. Jika sama, dipilih Koherensi terendah.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Integrasi jalur kereta api seringkali bukan peristiwa tunggal, melainkan bisa jadi proses yang bertahap dan membutuhkan waktu bertahun-tahun.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Roanoke and Tar River Railroad (R&TRR) adalah anak perusahaan Seaboard and Roanoke Railroad.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Roanoke and Tar River Railroad (R&TRR) terhubung di Boykins, Virginia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** Roanoke and Tar River Railroad (R&TRR) mengakuisisi Murfreesboro Railroad pada tahun 1893.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** Layanan di jalur Murfreesboro dihentikan pada tahun 1897.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Integrasi penuh Roanoke and Tar River Railroad ke dalam Seaboard Air Line Railway terjadi pada tahun 1900.
- FABLES: `UNFAITHFUL`
- RAGAS : `UNFAITHFUL`

**7. Klaim:** Roanoke and Tar River Railroad (R&TRR) sudah menjadi bagian dari sistem Seaboard Air Line melalui akuisisi bertahap oleh perusahaan-perusahaan pendahulu Seaboard Air Line Railway (SAL), seperti Raleigh and Gaston Railroad, sebelum nama SAL resmi digunakan.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**8. Klaim:** Tahun 1900 menandai penyelesaian integrasi administratif dan operasional yang membuat jalur Roanoke and Tar River Railroad beroperasi sepenuhnya di bawah bendera Seaboard Air Line Railway (SAL) sebagai bagian integral dari rute mereka.
- FABLES: `UNFAITHFUL`
- RAGAS : `UNFAITHFUL`

**9. Klaim:** Seaboard Air Line Railway adalah sebuah jaringan besar yang terbentuk pada tahun 1900.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**10. Klaim:** Seaboard Air Line Railway terbentuk pada tahun 1900 dengan menyatukan 19 jalur kereta api yang berbeda.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

