# Evaluasi Sampel Cerita (Sistem Bahasa Inggris - FAITHFULNESS - 5 Cerita)
Metode: **Disproportional Stratified Sampling** dengan **Hierarchical Metrik: Rata-rata Faithfulness (FABLES & RAGAS setara) > G-Eval Koherensi**.

## Evaluasi Sampel 1: SKOR TINGGI (Best Cases)
### Judul: Mei and the Moving Museum

- **Koherensi (G-Eval Norm):** `0.960`
- **Faithfulness (RAGAS):** `1.000`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness (RAGAS + FABLES) Max. Jika sama, dipilih Koherensi tertinggi.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Rute Trolleybus Shanghai 20 secara resmi mulai beroperasi pada 27 September 1928.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Rute Trolleybus Shanghai 20 menghubungkan The Bund, Nanjing Road, People's Square, dan Kuil Jing'an.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** The Bund memiliki bangunan bersejarah yang megah.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** Nanjing Road pernah menjadi jalan komersial utama di Tiongkok.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** People's Square adalah tengara perkotaan yang signifikan.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Kuil Jing'an adalah kuil Buddha kuno.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**7. Klaim:** Yingshang No. 1 tram adalah pendahulu langsung dari Rute Trolleybus Shanghai 20.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**8. Klaim:** Yingshang No. 1 tram dimulai dari The Bund dan Kuil Jing'an.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 2: SKOR TINGGI (Best Cases)
### Judul: Maya's Cosmic Quest: The PSLV-C56 Launch

- **Koherensi (G-Eval Norm):** `0.960`
- **Faithfulness (RAGAS):** `1.000`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness (RAGAS + FABLES) Max. Jika sama, dipilih Koherensi tertinggi.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** PSLV-C56 adalah sebuah misi peluncuran.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Indian Space Research Organisation (ISRO) memiliki situs web resmi.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Misi PSLV-C56 dijadwalkan untuk diluncurkan pada 30 Juli 2023, pukul 06:30 IST.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** Misi PSLV-C56 akan diluncurkan dari Satish Dhawan Space Centre (SDSC) SHAR, Sriharikota, India.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** Misi PSLV-C56 akan diluncurkan dari First Launch Pad (FLP) di Satish Dhawan Space Centre (SDSC) SHAR.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 3: SKOR SEDANG (Average Cases)
### Judul: The Emerald Isle's Economic Storm

- **Koherensi (G-Eval Norm):** `0.840`
- **Faithfulness (RAGAS):** `1.000`
- **Faithfulness (FABLES):** `1.000`
- **Alasan Pemilihan:** Jarak 3D terdekat dengan Median Sistem: Koherensi (0.850), RAGAS (1.000), dan FABLES (1.000).

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Utang luar negeri Sri Lanka mencapai 119% dari PDB pada tahun 2021.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Sri Lanka hanya memiliki $2,31 miliar cadangan pada Februari 2022.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Sri Lanka menghadapi pembayaran utang sekitar $4 miliar untuk tahun 2022.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**4. Klaim:** Sri Lanka mulai banyak meminjam dari pasar internasional swasta melalui 'obligasi negara'.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** Obligasi negara memiliki suku bunga yang lebih tinggi dan waktu pembayaran yang lebih singkat.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Hampir setengah dari utang luar negeri Sri Lanka berasal dari obligasi negara.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**7. Klaim:** Pada April 2021, pemerintah Sri Lanka melarang pupuk kimia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**8. Klaim:** Pemerintah Sri Lanka ingin beralih sepenuhnya ke pertanian organik.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**9. Klaim:** Panen padi di Sri Lanka turun 32% setelah larangan pupuk kimia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**10. Klaim:** Produksi teh di Sri Lanka turun 18% setelah larangan pupuk kimia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 4: SKOR RENDAH (Worst Cases)
### Judul: Leo and the Mystery of the Meadow Bees

- **Koherensi (G-Eval Norm):** `0.920`
- **Faithfulness (RAGAS):** `0.733`
- **Faithfulness (FABLES):** `0.917`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness Min. Jika sama, dipilih Koherensi terendah.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Taksonomi adalah ilmu yang mengklasifikasikan makhluk hidup.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Taksonomi membantu memahami keanekaragaman hayati.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Lebah *Dasypoda* memiliki tubuh berbulu dan kaki panjang yang sempurna untuk mengumpulkan serbuk sari.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**4. Klaim:** Lebah *Dasypoda* memiliki rambut khusus di kakinya, yang disebut sikat serbuk sari, yang digunakan untuk mengumpulkan serbuk sari.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**5. Klaim:** Dasypoda radchenkoi* dan *Dasypoda morotei* memiliki morfologi yang sangat mirip.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Kesamaan visual dapat menyesatkan dalam taksonomi.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**7. Klaim:** DNA adalah instruksi unik untuk setiap makhluk hidup.
- FABLES: `CANT_VERIFY`
- RAGAS : `UNFAITHFUL`

**8. Klaim:** Perbedaan kecil dalam DNA dapat menunjukkan seberapa dekat hubungan dua spesies.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**9. Klaim:** Dasypoda radchenkoi* adalah spesies terpisah dari *Dasypoda morotei*.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**10. Klaim:** Dasypoda radchenkoi* termasuk dalam subgenus *Heterodasypoda*.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

## Evaluasi Sampel 5: SKOR RENDAH (Worst Cases)
### Judul: The Tremor's Truth

- **Koherensi (G-Eval Norm):** `0.940`
- **Faithfulness (RAGAS):** `0.800`
- **Faithfulness (FABLES):** `0.889`
- **Alasan Pemilihan:** 1 dari 2 cerita dengan rata-rata Faithfulness Min. Jika sama, dipilih Koherensi terendah.

### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)
*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*

**1. Klaim:** Bencana alam berdampak pada komunitas di seluruh dunia.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**2. Klaim:** Gempa bumi Hormozgan 2022 adalah serangkaian gempa bumi.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**3. Klaim:** Gempa bumi Hormozgan 2022 yang terkuat mencapai magnitudo maksimum 6.3.
- FABLES: `UNFAITHFUL`
- RAGAS : `UNFAITHFUL`

**4. Klaim:** Guncangan utama gempa bumi Hormozgan 2022 adalah peristiwa magnitudo 6.0.
- FABLES: `UNFAITHFUL`
- RAGAS : `UNFAITHFUL`

**5. Klaim:** Guncangan utama gempa bumi Hormozgan 2022 diikuti oleh gempa susulan magnitudo 5.7.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**6. Klaim:** Gempa bumi Hormozgan 2022 diikuti oleh gempa bumi magnitudo 6.0 lainnya.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**7. Klaim:** Gempa bumi Hormozgan 2022 mengakibatkan tujuh kematian.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**8. Klaim:** Gempa bumi Hormozgan 2022 mengakibatkan 111 orang lainnya terluka.
- FABLES: `PARTIAL_SUPPORT`
- RAGAS : `PARTIAL_SUPPORT`

**9. Klaim:** Setidaknya 22 dari korban luka gempa bumi Hormozgan 2022 memerlukan rawat inap.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

**10. Klaim:** Skala Richter membantu memahami kekuatan ilmiah gempa bumi.
- FABLES: `FAITHFUL`
- RAGAS : `FAITHFUL`

---

