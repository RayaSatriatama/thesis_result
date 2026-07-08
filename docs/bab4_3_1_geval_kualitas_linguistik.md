# Bab 4.3.1 G-Eval: Kualitas Linguistik (DeepEval)

Evaluasi koherensi naratif pada cerita anak edukatif dalam penelitian ini diawali dengan penilaian otomatis berbasis aspek kebahasaan menggunakan kerangka kerja G-Eval yang diintegrasikan melalui pustaka DeepEval. Penggunaan G-Eval bertujuan untuk mengukur kualitas penulisan cerita secara terstandardisasi pada lima dimensi linguistik utama yang relevan dengan kebutuhan materi pembelajaran anak usia sekolah. Kelima dimensi tersebut meliputi *Clarity* (kejelasan bahasa), *Fluency* (kefasihan tata bahasa), *Consistency* (konsistensi suara naratif), *Repetitiveness* (tingkat redundansi), dan *Conciseness* (keringkasan alur cerita).

## 1. Parameter dan Relevansi Dimensi G-Eval dalam Cerita Edukatif

Penilaian koherensi naratif anak memerlukan pendekatan yang berbeda dari teks umum. Narasi edukasi harus mampu menyederhanakan materi sains, sejarah, atau konsep abstrak lainnya tanpa kehilangan daya tarik sastrawi. Berikut adalah penjelasan parameter penilaian G-Eval beserta relevansinya dalam domain cerita edukatif anak:

*   **Clarity (Kejelasan):** Mengukur kemampuan cerita dalam menyajikan informasi dan pesan secara gamblang serta menghindari jargon teknis yang membingungkan. Dimensi ini krusial untuk memastikan anak usia sasaran dapat memahami konsep inti pembelajaran (seperti hukum fisika, taksonomi biologi, atau fakta sejarah) tanpa terdistraksi oleh struktur kalimat yang membingungkan.
*   **Fluency (Kefasihan):** Menilai ketepatan tata bahasa, sintaksis, dan kelancaran aliran antarkalimat. Kefasihan penulisan sangat penting untuk kenyamanan membaca anak-anak yang masih dalam tahap pengembangan kemampuan literasi dasar, sehingga terhindar dari konstruksi frasa yang canggung.
*   **Consistency (Konsistensi):** Menilai konsistensi gaya bahasa, nada (*tone*), dan sudut pandang naratif (*narrative voice*) dari awal hingga akhir cerita. Dalam cerita edukasi, stabilitas nada cerita (misalnya dari sudut pandang orang ketiga yang hangat dan memotivasi) sangat penting untuk menjaga fokus emosional anak.
*   **Repetitiveness (Ketidak-repetitifan):** Mengukur keunikan informasi dan ketiadaan pengulangan ide atau frasa secara berlebihan. Cerita yang terlalu repetitif akan menurunkan minat baca anak, sehingga dimensi ini menilai efisiensi penyampaian ide-ide unik dalam teks.
*   **Conciseness (Keringkasan):** Menilai ketiadaan kata penjelas yang tidak perlu (*filler words*) dan efektivitas pembagian paragraf. Keringkasan memastikan cerita langsung berfokus pada inti narasi dan pesan moral tanpa bertele-tele, sehingga mampu mengimbangi keterbatasan rentang perhatian (*attention span*) anak.

Skor untuk kelima sub-kriteria di atas diukur menggunakan skala ordinal 1 sampai dengan 5 (dengan 5 sebagai skor terbaik). Untuk keperluan agregasi statistik global dan perbandingan lintas model, nilai mentah tersebut dinormalisasi ke skala kontinu 0 sampai dengan 1 melalui formula berikut:

$$\text{Skor Normalisasi} = \frac{\text{Skor Mentah} - 1}{4}$$

## 2. Analisis Statistik Deskriptif dan Sebaran Skor Coherence

Pengujian koherensi naratif dilakukan terhadap populasi sebanyak 100 cerita yang dihasilkan oleh sistem berbasis agen (*Agentic* AI) (50 cerita berbahasa Indonesia dan 50 cerita berbahasa Inggris). Berdasarkan data observasi otomatis, diperoleh ringkasan statistik deskriptif dari skor normalisasi koherensi G-Eval sebagai berikut:

| Metrik Statistik | Nilai Skor Normalisasi (Skala 0-1) |
| :--- | :---: |
| Jumlah Sampel ($N$) | 100 |
| Rata-rata (*Mean*) | 0,8630 |
| Deviasi Standar (*Std Dev*) | 0,0957 |
| Skor Minimum (*Min*) | 0,4200 |
| Kuartil Bawah ($Q_1$ - 25%) | 0,8200 |
| Median ($Q_2$ - 50%) | 0,9000 |
| Kuartil Atas ($Q_3$ - 75%) | 0,9250 |
| Skor Maksimum (*Max*) | 0,9800 |

Secara keseluruhan, rata-rata skor koherensi normalisasi yang dicapai oleh sistem adalah sebesar 0,8630 (setara dengan nilai mentah rata-rata 4,452 dari skala 5). Nilai median yang menyentuh angka 0,9000 mengindikasikan bahwa sebagian besar cerita yang diproduksi oleh agen memiliki kualitas koherensi dan estetika bahasa yang sangat baik.

Berbeda dengan skor *faithfulness* RAGAS yang menunjukkan *ceiling effect* (efek langit-langit) yang sangat ekstrem, sebaran skor koherensi naratif ini lebih bervariasi dengan deviasi standar sebesar 0,0957 dan nilai minimum yang mencapai 0,4200. Hal ini membuktikan bahwa metrik G-Eval memiliki tingkat sensitivitas yang memadai untuk mendeteksi fluktuasi kualitas alur narasi, sehingga tidak semua cerita terpusat pada nilai sempurna.

Visualisasi distribusi dan ringkasan performa dimensi G-Eval ini dapat dilihat pada gambar di bawah ini:

![Visualisasi Distribusi dan Statistik Koherensi G-Eval](/mnt/nvme0n1p4/Projects/Programming_Projects/Skripsi/assets/evaluation/4.3.1_geval_coherence_stats.png)

## 3. Analisis Variansi per Dimensi Kebahasaan

Untuk mengidentifikasi aspek linguistik mana yang paling konsisten dan mana yang paling bervariasi, data mentah (skala 1 sampai dengan 5) dari kelima dimensi G-Eval dianalisis secara terpisah. Ringkasan performa per dimensi disajikan dalam tabel berikut:

| Aspek Dimensi | Rata-rata (*Mean*) | Deviasi Standar (*Std*) | Skor Minimum (*Min*) | Skor Maksimum (*Max*) |
| :--- | :---: | :---: | :---: | :---: |
| **Clarity** | 4,81 | 0,75 | 1,00 | 5,00 |
| **Fluency** | 4,70 | 0,72 | 3,00 | 5,00 |
| **Repetitiveness** | 4,58 | 0,78 | 3,00 | 5,00 |
| **Consistency** | 4,53 | 0,85 | 3,00 | 5,00 |
| **Conciseness** | 4,25 | 0,50 | 3,00 | 5,00 |

Berdasarkan data variansi kelima dimensi kebahasaan tersebut, profil luaran linguistik sistem dapat dideskripsikan sebagai berikut:

1.  **Clarity (4,81) dan Fluency (4,70):** Kedua dimensi dasar ini mencatat skor rata-rata tertinggi dan hampir menyentuh nilai maksimal. Teks yang dihasilkan terpantau sangat bersih dari kesalahan tata bahasa teknis dan memiliki struktur kalimat aktif yang sangat mudah dipahami oleh pembaca.
2.  **Repetitiveness (4,58) dan Consistency (4,53):** Aspek repetisi dan konsistensi naratif berada pada rentang nilai yang sangat stabil. Teks cerita terpantau mampu mempertahankan kelurusan sudut pandang tokoh utama tanpa adanya pengulangan informasi faktual secara berlebihan.
3.  **Conciseness (4,25):** Dimensi keringkasan alur mencatat skor rata-rata terendah di antara yang lain. Hal ini mengindikasikan adanya kecenderungan luaran teks yang sedikit panjang lebar (*verbose*) berupa penambahan deskripsi latar belakang atau kalimat dramatisasi pada bagian penutup cerita. Meskipun demikian, skor 4,25 tetap berada pada kategori sangat baik, menandakan bahwa kepadatan narasi masih berada dalam batas kewajaran bacaan anak.

Pengujian statistik lebih lanjut untuk membuktikan apakah profil tingginya skor di atas merupakan kontribusi nyata dari orkestrasi berbasis agen atau sekadar kemampuan bawaan model fondasi (*baseline*) akan dibedah secara komparatif pada subbab 4.3.4.

## 4. Perbandingan Koherensi Lintas Bahasa (Bahasa Indonesia vs Bahasa Inggris)

Evaluasi kebahasaan juga ditujukan untuk mendeteksi apakah terdapat perbedaan kualitas koherensi yang dipengaruhi oleh bahasa instruksi dan keluaran. Perbandingan statistik deskriptif skor normalisasi koherensi antara sub-populasi cerita berbahasa Inggris (EN) dan cerita berbahasa Indonesia (ID) dijabarkan pada tabel di bawah ini:

| Metrik Statistik | Bahasa Inggris (EN) | Bahasa Indonesia (ID) |
| :--- | :---: | :---: |
| Jumlah Sampel ($N$) | 50 | 50 |
| Rata-rata (*Mean*) | 0,8500 | 0,8760 |
| Deviasi Standar (*Std Dev*) | 0,1096 | 0,0784 |
| Skor Minimum (*Min*) | 0,4200 | 0,6400 |
| Kuartil Bawah ($Q_1$ - 25%) | 0,8200 | 0,8200 |
| Median ($Q_2$ - 50%) | 0,8900 | 0,9000 |
| Kuartil Atas ($Q_3$ - 75%) | 0,9200 | 0,9400 |
| Skor Maksimum (*Max*) | 0,9600 | 0,9800 |

Berdasarkan perbandingan tersebut, cerita anak berbahasa Indonesia memiliki rata-rata skor koherensi sedikit lebih tinggi (+0,0260 atau +2,6%) dibandingkan cerita berbahasa Inggris. Selain itu, variabilitas cerita berbahasa Indonesia juga lebih stabil dengan deviasi standar yang lebih kecil (0,0784) dibandingkan cerita berbahasa Inggris (0,1096).

Faktor utama yang menyebabkan variabilitas cerita berbahasa Inggris lebih tinggi adalah adanya beberapa kasus pencilan ekstrem berdaya koherensi rendah, salah satunya adalah *Story 4 EN (Alex and the PharmaCann Mystery)* dengan skor koherensi normalisasi terendah sebesar 0,4200. Kegagalan koherensi pada pencilan tersebut disebabkan oleh kecenderungan model pembuat cerita berbahasa Inggris untuk memproduksi gaya fiksi naratif murni yang mengabaikan instruksi format penjelasan faktual terstruktur, sehingga dinilai buruk pada aspek kejelasan (*Clarity*) oleh evaluator otomatis G-Eval. Sebaliknya, sub-populasi cerita berbahasa Indonesia menunjukkan batas bawah yang lebih tinggi (0,6400) dan distribusi yang lebih merata di sekitar angka median 0,9000. Hal ini membuktikan efektivitas lokalisasi agen dalam menjaga alur cerita tetap edukatif sekaligus berdaya koherensi tinggi.
