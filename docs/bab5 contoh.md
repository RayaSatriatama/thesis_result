5.1 Kesimpulan
Berdasarkan hasil temuan yang dilakukan pada penelitian ini, terdapat beberapa
kesimpulan yang dapat diambil, diantaranya:
1) Large Language Model (LLM) berbasis Llama 3.2 varian 1B
memungkinkan proses fine-tuning menggunakan framework yang
disediakan oleh Unsloth terhadap domain spesifik seperti text-generation
yang berfokus pada bidang emosi atau pendekatan secara afektif. Hal ini
ditunjukkan dengan perbedaan nilai yang dihasilkan metrik ROUGE dan
BERTScore dimana fine-tuned model mendapat nilai rata-rata sebesar 0,098
pada metrik ROUGE, dan 0,7240 pada metrik BERTScore. Nilai ROUGE
yang rendah menunjukkan bahwa model dapat membuat teks dengan varian
yang jauh berbeda dibandingkan data latih sehingga tidak menunjukkan
indikasi overfit, dimana model menghafal data dibandingkan
mempelajarinya. Kemudian, nilai BERTScore yang cukup tinggi
menandakan bahwa model dapat membuat teks yang memiliki kemiripan
konteks dengan data latih sehingga data yang dibuat memiliki makna dengan
konotasi yang mirip. Selain itu, saat proses training, model menghasilkan
nilai loss yang menurun secara bertahap, baik pada nilai train loss maupun
validation loss sehingga tidak terdapat indikasi overfit maupun underfit.
2) Berdasarkan hasil evaluasi oleh metrik ROUGE dan BERTScore yang
menunjukkan bahwa model hasil fine-tuning unggul sekitar 6,8% pada
metrik ROUGE, dan 3,6% pada metrik BERTScore dibandingkan dengan
base model dari Llama 3.2 varian 1B, dapat disimpulkan bahwa proses finetuning memiliki dampak dalam mendorong model menghasilkan teks
intervensi afektif yang lebih mirip secara makna dan kualitas kata-per-kata
yang jauh berbeda dengan data referensi yang ada. Hal ini sekaligus
menunjukkan bahwa proses fine-tuning memiliki potensi untuk memberikan
hasil yang lebih baik pada tugas text-generation yang dapat diukur
menggunakan ROUGE maupun BERTScore pada Large Language Model
(LLM).
5.2 Implikasi
Penerapan proses fine-tuning menggunakan framework Unsloth pada Large
Language Model (LLM) berbasis Llama 3.2 varian 1B pada tugas respon teks
intervensi afektif dapat menghasilkan model dengan kualitas respon yang
memuaskan pada domain tersebut, yang diukur melalui metrik ROUGE dengan
menghitung frekuensi kemunculan kata serupa, dan metrik BERTScore yang
menghitung nilai kemiripan makna dari teks yang dihasilkan. ini diharapkan dapat
memberikan kontribusi dalam bidang emosi dalam pembelajaran, khususnya
spesifik pada domain emosi. Implikasi ini dapat dijadikan sebagai referensi bagi
peneliti yang akan melanjutkan penelitian dengan topik yang serupa.
5.3 Rekomendasi
Meskipun model yang dihasilkan telah mendapatkan nilai pengujian yang cukup
baik, beberapa saran dan rekomendasi berikut dapat dijadikan bahan pertimbangan
untuk meningkatkan hasil uji serta mengarahkan penelitian ini ke tahap berikutnya.
Berdasarkan rangkaian penelitian dan hasil pengujian yang telah dilakukan,
terdapat beberapa rekomendasi yang diusulkan untuk penelitian selanjutnya, di
antaranya adalah sebagai berikut.
1) Mengeksplorasi lebih lanjut terhadap penggunaan Large Language Model
(LLM) lain seperti varian yang lebih tinggi dari Llama 3.2 varian 1B,
penggunaan model teks lain seperti Mistral 7B, Phi 3.5, dan Gemma 2 yang
disediakan oleh framework Unsloth, maupun model open-source lain
seperti DeepSeek.
2) Menggunakan framework lain selain Unsloth yang dapat mempercepat
proses inference pada pembuatan respon sehingga menghasilkan model
dengan performa yang jauh lebih optimal pada penggunaan sistem dengan
spesifikasi yang hanya mengandalkan CPU.
3) Melibatkan pengujian secara langsung pada responden untuk melihat
dampak dari respon yang dihasilkan baik oleh fine-tuned model maupun
base model sehingga dapat menjadi bahan pertimbangan tambahan terkait
kesuksesan penerapan Large Language Model (LLM) sebagai alat untuk
menghasilkan teks intervensi afektif pada domain emosi pembelajaran. 