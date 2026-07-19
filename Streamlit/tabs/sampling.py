import streamlit as st
import pandas as pd
import numpy as np
from lib.faithfulness_metrics import load_all_traces_df

def get_samples_for_lang_and_priority(df_all, prompt_filter, priority):
    df = df_all[df_all["input"].astype(str).str.contains(prompt_filter, na=False)].copy()

    metrik_utama = "geval_coherence_normalized"
    if metrik_utama not in df.columns and "geval_coherence_raw" in df.columns:
        metrik_utama = "geval_coherence_raw"
        
    metrik_sekunder_1 = "ragas_standard_faithfulness"
    metrik_sekunder_2 = "fables_faithfulness"

    df_valid = df.dropna(subset=[metrik_utama, metrik_sekunder_1, metrik_sekunder_2]).copy()
    if len(df_valid) == 0:
        return pd.DataFrame()

    if priority == "Faithfulness":
        sort_metrics = [metrik_sekunder_2, metrik_sekunder_1, metrik_utama]
    else:
        sort_metrics = [metrik_utama, metrik_sekunder_1, metrik_sekunder_2]

    asc_high = [False, False, False]
    asc_low = [True, True, True]

    s_tinggi = df_valid.sort_values(by=sort_metrics, ascending=asc_high).head(2).copy()
    s_tinggi['Kategori'] = "SKOR TINGGI (Best Cases)"
    df_valid = df_valid.drop(s_tinggi.index)

    s_rendah = df_valid.sort_values(by=sort_metrics, ascending=asc_low).head(2).copy()
    s_rendah['Kategori'] = "SKOR RENDAH (Worst Cases)"
    df_valid = df_valid.drop(s_rendah.index)

    median_coh = df_valid[metrik_utama].median()
    median_ragas = df_valid[metrik_sekunder_1].median()
    median_fables = df_valid[metrik_sekunder_2].median()

    df_valid['jarak_sentral'] = np.sqrt(
        (df_valid[metrik_utama] - median_coh)**2 +
        (df_valid[metrik_sekunder_1] - median_ragas)**2 +
        (df_valid[metrik_sekunder_2] - median_fables)**2
    )
    s_sedang = df_valid.sort_values('jarak_sentral', ascending=True).head(1).copy()
    s_sedang['Kategori'] = "SKOR SEDANG (Average Case)"

    res = pd.concat([s_tinggi, s_sedang, s_rendah])
    res['Prioritas'] = priority
    return res

def render_sampling_tab():
    st.header("Analisis Stratified Purposive Sampling (Expert Judgement)")
    st.markdown(
        "Tabel berikut menunjukkan keseluruhan 20 sampel cerita yang dievaluasi oleh ahli materi. "
        "Sampel dipilih menggunakan **Disproportional Stratified Purposive Sampling** (Maximum Variation). "
        "Setiap dimensi evaluasi (Koherensi Naratif dan Faithfulness) memiliki 10 sampel (5 Bahasa Inggris, 5 Bahasa Indonesia), "
        "mewakili spektrum kinerja terbaik (Top 2), kinerja rata-rata, dan kinerja terburuk (Bottom 2)."
    )

    try:
        df_all = load_all_traces_df()
    except Exception as e:
        st.error("Gagal memuat data traces.")
        return

    # Generate 20 samples
    samples = []
    
    # 1. Faithfulness EN
    s_f_en = get_samples_for_lang_and_priority(df_all, "Create an", "Faithfulness")
    if not s_f_en.empty:
        s_f_en['Bahasa'] = "Inggris"
        samples.append(s_f_en)
        
    # 2. Faithfulness ID
    s_f_id = get_samples_for_lang_and_priority(df_all, "Buat cerita", "Faithfulness")
    if not s_f_id.empty:
        s_f_id['Bahasa'] = "Indonesia"
        samples.append(s_f_id)
        
    # 3. Coherence EN
    s_c_en = get_samples_for_lang_and_priority(df_all, "Create an", "Coherence")
    if not s_c_en.empty:
        s_c_en['Bahasa'] = "Inggris"
        samples.append(s_c_en)
        
    # 4. Coherence ID
    s_c_id = get_samples_for_lang_and_priority(df_all, "Buat cerita", "Coherence")
    if not s_c_id.empty:
        s_c_id['Bahasa'] = "Indonesia"
        samples.append(s_c_id)

    if not samples:
        st.warning("Tidak ada data valid yang bisa ditampilkan.")
        return

    df_final = pd.concat(samples)
    
    # Parse Judul if needed
    import json
    def parse_title(out):
        if isinstance(out, str):
            try:
                import ast
                parsed_str = ast.literal_eval(out) if out.strip().startswith(('"',"'")) else out
                parsed_dict = json.loads(parsed_str) if isinstance(parsed_str, str) else parsed_str
                if isinstance(parsed_dict, str):
                    parsed_dict = json.loads(parsed_dict)
                return parsed_dict.get('draft_title', 'Tanpa Judul')
            except:
                return 'Tanpa Judul'
        elif isinstance(out, dict):
            return out.get('draft_title', 'Tanpa Judul')
        return 'Tanpa Judul'
        
    df_final['Judul'] = df_final['output'].apply(parse_title)
    
    # Select columns to display
    mu = "geval_coherence_normalized" if "geval_coherence_normalized" in df_final.columns else "geval_coherence_raw"
    display_cols = ['Prioritas', 'Bahasa', 'Kategori', 'Judul', mu, 'ragas_standard_faithfulness', 'fables_faithfulness']
    
    df_show = df_final[display_cols].copy()
    
    # Format floats
    df_show[mu] = df_show[mu].map("{:.3f}".format)
    df_show['ragas_standard_faithfulness'] = df_show['ragas_standard_faithfulness'].map("{:.3f}".format)
    df_show['fables_faithfulness'] = df_show['fables_faithfulness'].map("{:.3f}".format)
    
    # Rename columns for clarity
    df_show = df_show.rename(columns={
        mu: 'Koherensi (G-Eval)',
        'ragas_standard_faithfulness': 'Faithfulness (RAGAS)',
        'fables_faithfulness': 'Faithfulness (FABLES)'
    })

    st.subheader("Data Keseluruhan 20 Sampel Terpilih")
    st.dataframe(df_show, use_container_width=True)
