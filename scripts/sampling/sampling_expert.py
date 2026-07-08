import pandas as pd
import numpy as np
import ast
import glob
import os

# ==============================================================================
# SCRIPT STRATIFIED PURPOSIVE SAMPLING (DISPROPORTIONAL 4-3-3)
# ==============================================================================
# Teknik: Maximum Variation berbasis Hirarki Metrik.
# Kriteria Utama: Narrative Coherence (geval_coherence_normalized)
# Kriteria Sekunder: Faithfulness (ragas_standard_faithfulness)
#
# Alasan Pemilihan Teknik:
# Untuk expert judgement, peneliti menggunakan sampel 10 cerita (disproportional):
# - 4 cerita terbaik (Tinggi) agar proporsional dengan sebaran data asli (negative skew).
# - 3 cerita standar (Sedang) representasi kinerja rata-rata.
# - 3 cerita terburuk (Rendah) sengaja dilebihkan (oversampling) untuk memvalidasi
#   kemampuan evaluasi otomatis (LLM-as-a-Judge) dalam mendeteksi halusinasi/inkoherensi.
# ==============================================================================

def parse_metric(v):
    if pd.isna(v) or v == '' or v == '[]': return np.nan
    try:
        parsed = ast.literal_eval(str(v))
        if isinstance(parsed, list):
            vals = [float(x) for x in parsed if x != '']
            return np.mean(vals) if vals else np.nan
        return float(parsed)
    except:
        try: return float(v)
        except: return np.nan

def get_latest_trace_df():
    # Load traces dari root folder
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    traces_path = os.path.join(base_dir, 'Eval_Data', 'Traces', '*.csv')
    files = glob.glob(traces_path)
    if not files:
        raise FileNotFoundError(f"Tidak ada file CSV di {traces_path}")
    latest_file = max(files, key=os.path.getmtime)
    df = pd.read_csv(latest_file)

    # Bersihkan kutip ganda HANYA dari kolom 'id' agar traceId cocok dengan JSONL
    if 'id' in df.columns:
        df['id'] = df['id'].astype(str).str.strip('"')

    # Parse metrik
    df['geval_coherence_normalized'] = df.get('geval_coherence_normalized', pd.Series(dtype=float)).apply(parse_metric)
    df['ragas_standard_faithfulness'] = df.get('ragas_standard_faithfulness', pd.Series(dtype=float)).apply(parse_metric)
    df['fables_faithfulness'] = df.get('fables_faithfulness', pd.Series(dtype=float)).apply(parse_metric)
    return df

def get_observation_critics(trace_ids):
    import json
    import glob
    import os

    # Load observasi terbaru
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    obs_path = os.path.join(base_dir, 'Eval_Data', 'Observations', '*.jsonl')
    files = glob.glob(obs_path)
    if not files:
        return {}

    latest_obs = max(files, key=os.path.getmtime)

    critics = {}
    with open(latest_obs, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                trace_id = data.get('traceId')
                name = data.get('name')

                if trace_id in trace_ids:
                    if trace_id not in critics:
                        critics[trace_id] = {'geval': {}, 'claims': []}
                        
                    # 1. Parsing G-Eval
                    if name and name.startswith('geval_'):
                        output = data.get('output', {})
                        if isinstance(output, str):
                            try:
                                output = json.loads(output)
                            except:
                                pass
                                
                        if isinstance(output, dict) and 'reason' in output:
                            sub_metric = name.replace('geval_', '').capitalize()
                            score = output.get('score', 'N/A')
                            reason = output.get('reason', 'N/A')
                            critics[trace_id]['geval'][sub_metric] = f"**Skor {score}:** {reason}"
                    
                    # 2. Parsing FABLES/RAGAS Claims
                    elif name == 'fables_verify_all_claims':
                        output = data.get('output', {})
                        if isinstance(output, str):
                            try:
                                output = json.loads(output)
                            except:
                                pass
                        
                        if isinstance(output, dict) and 'verdicts' in output:
                            critics[trace_id]['claims'] = output.get('verdicts', [])
            except:
                pass
    return critics

def generate_sample_for_lang(df_all, critics_data, lang_name, prompt_filter, file_suffix, priority="coherence"):
    # Filter KHUSUS untuk sistem bahasa tertentu
    df = df_all[df_all['input'].astype(str).str.contains(prompt_filter, na=False)].copy()
    
    metrik_utama = 'geval_coherence_normalized'
    metrik_sekunder_1 = 'ragas_standard_faithfulness'
    metrik_sekunder_2 = 'fables_faithfulness'
    
    # Filter data valid
    df_valid = df.dropna(subset=[metrik_utama, metrik_sekunder_1, metrik_sekunder_2]).copy()

    if priority == "faithfulness":
        df_valid['faithfulness_avg'] = (df_valid[metrik_sekunder_1] + df_valid[metrik_sekunder_2]) / 2.0
        sort_metrics = ['faithfulness_avg', metrik_utama]
        asc_high = [False, False]
        asc_low = [True, True]
        metode_desc = "**Hierarchical Metrik: Rata-rata Faithfulness (FABLES & RAGAS setara) > G-Eval Koherensi**."
        alasan_tinggi = "1 dari 2 cerita dengan rata-rata Faithfulness (RAGAS + FABLES) Max. Jika sama, dipilih Koherensi tertinggi."
        alasan_rendah = "1 dari 2 cerita dengan rata-rata Faithfulness Min. Jika sama, dipilih Koherensi terendah."
    else:
        sort_metrics = [metrik_utama, metrik_sekunder_1, metrik_sekunder_2]
        asc_high = [False, False, False]
        asc_low = [True, True, True]
        metode_desc = "**Hierarchical Metrik 3D: G-Eval (Prioritas 1) > RAGAS (Prioritas 2) > FABLES (Prioritas 3)**."
        alasan_tinggi = "1 dari 2 cerita dengan skor Max. Koherensi tertinggi. Jika ada yang sama, dipilih RAGAS tertinggi, lalu FABLES tertinggi secara berurutan."
        alasan_rendah = "1 dari 2 cerita dengan skor Min. Koherensi terendah. Bertujuan memvalidasi kegagalan sistem pada RAGAS dan FABLES yang juga terendah."

    # 1. Kinerja TINGGI (2 Sampel)
    s_tinggi = df_valid.sort_values(
        by=sort_metrics,
        ascending=asc_high
    ).head(2)
    s_tinggi['kategori'] = "SKOR TINGGI (Best Cases)"
    s_tinggi['alasan_pilih'] = alasan_tinggi
    df_valid = df_valid.drop(s_tinggi.index)

    # 2. Kinerja RENDAH (2 Sampel)
    s_rendah = df_valid.sort_values(
        by=sort_metrics,
        ascending=asc_low
    ).head(2)
    s_rendah['kategori'] = "SKOR RENDAH (Worst Cases)"
    s_rendah['alasan_pilih'] = alasan_rendah
    df_valid = df_valid.drop(s_rendah.index)

    # 3. Kinerja SEDANG (1 Sampel)
    median_coh = df_valid[metrik_utama].median()
    median_ragas = df_valid[metrik_sekunder_1].median()
    median_fables = df_valid[metrik_sekunder_2].median()

    df_valid['jarak_sentral_3d'] = np.sqrt(
        (df_valid[metrik_utama] - median_coh)**2 +
        (df_valid[metrik_sekunder_1] - median_ragas)**2 +
        (df_valid[metrik_sekunder_2] - median_fables)**2
    )
    s_sedang = df_valid.sort_values('jarak_sentral_3d', ascending=True).head(1)
    s_sedang['kategori'] = "SKOR SEDANG (Average Cases)"
    s_sedang['alasan_pilih'] = f"Jarak 3D terdekat dengan Median Sistem: Koherensi ({median_coh:.3f}), RAGAS ({median_ragas:.3f}), dan FABLES ({median_fables:.3f})."

# Gabung dan format output
    df_expert = pd.concat([s_tinggi, s_sedang, s_rendah])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_stories = os.path.join(script_dir, f"expert_judgement_stories_{priority}_{file_suffix}.md")
    out_evals = os.path.join(script_dir, f"expert_judgement_evals_{priority}_{file_suffix}.md")

    import json

    with open(out_stories, 'w', encoding='utf-8') as f_story, open(out_evals, 'w', encoding='utf-8') as f_eval:
        f_story.write(f"# Sampel Cerita ({lang_name} - {priority.upper()} - 5 Cerita)\n\n")
        f_eval.write(f"# Evaluasi Sampel Cerita ({lang_name} - {priority.upper()} - 5 Cerita)\n")
        f_eval.write(f"Metode: **Disproportional Stratified Sampling** dengan {metode_desc}\n\n")

        counter = 1
        for idx, row in df_expert.iterrows():
            trace_id = row['id']
            coh_score = row[metrik_utama]
            ragas_score = row[metrik_sekunder_1]
            fables_score = row[metrik_sekunder_2]
            kategori = row['kategori']
            alasan = row['alasan_pilih']
            pertanyaan = row.get('input', 'N/A')
            raw_cerita = row.get('output', 'N/A')

            judul_cerita = "Tanpa Judul"
            cerita_final = str(raw_cerita)

            if isinstance(raw_cerita, str):
                parsed_dict = None
                try:
                    import ast
                    parsed_str = ast.literal_eval(raw_cerita) if raw_cerita.strip().startswith(('"',"'")) else raw_cerita
                    parsed_dict = json.loads(parsed_str) if isinstance(parsed_str, str) else parsed_str
                except Exception as e:
                    try:
                        parsed_dict = json.loads(raw_cerita)
                    except:
                        pass

                if isinstance(parsed_dict, str):
                    try:
                        parsed_dict = json.loads(parsed_dict)
                    except:
                        pass

                if isinstance(parsed_dict, dict):
                    judul_cerita = parsed_dict.get('draft_title', 'Tanpa Judul')
                    cerita_final = parsed_dict.get('final_story', cerita_final)

            critic = critics_data.get(trace_id, {'geval': {}, 'claims': []})
            
            # --- Tulis ke File Stories ---
            f_story.write(f"## Sampel {counter}: {kategori}\n")
            f_story.write(f"### Judul: {judul_cerita}\n\n")
            f_story.write(f"**Prompt / Input:**\n> {pertanyaan}\n\n")
            f_story.write(f"**Cerita:**\n\n{cerita_final}\n\n")
            f_story.write("---\n\n")
            
            # --- Tulis ke File Evaluations ---
            f_eval.write(f"## Evaluasi Sampel {counter}: {kategori}\n")
            f_eval.write(f"### Judul: {judul_cerita}\n\n")
            f_eval.write(f"- **Koherensi (G-Eval Norm):** `{coh_score:.3f}`\n")
            f_eval.write(f"- **Faithfulness (RAGAS):** `{ragas_score:.3f}`\n")
            f_eval.write(f"- **Faithfulness (FABLES):** `{fables_score:.3f}`\n")
            f_eval.write(f"- **Alasan Pemilihan:** {alasan}\n\n")
            
            # Bedakan output evaluasi berdasarkan prioritas metrik
            if priority == "faithfulness":
                claims = critic.get('claims', [])
                if claims:
                    f_eval.write(f"### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)\n")
                    f_eval.write(f"*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*\n\n")
                    for i, c in enumerate(claims, 1):
                        verdict = c.get('verdict', 'UNKNOWN')
                        fables_label = verdict
                        ragas_label = "UNFAITHFUL" if verdict == "CANT_VERIFY" else verdict
                        
                        f_eval.write(f"**{i}. Klaim:** {c.get('claim', '')}\n")
                        f_eval.write(f"- FABLES: `{fables_label}`\n")
                        f_eval.write(f"- RAGAS : `{ragas_label}`\n\n")
            else:
                # Prioritas COHERENCE: tampilkan alasan G-Eval
                geval_data = critic.get('geval', {})
                if geval_data:
                    f_eval.write(f"### Alasan Penilaian G-Eval (LLM-as-a-Judge)\n")
                    for sub_metric, reason in geval_data.items():
                        f_eval.write(f"- **{sub_metric}:** {reason}\n")
                    f_eval.write("\n")

            f_eval.write("---\n\n")
            counter += 1

    print(f"Berhasil membuat {out_stories} dan {out_evals}")

def generate_sample_md():
    df_all = get_latest_trace_df()

    trace_ids = set(df_all['id'].tolist())
    critics_data = get_observation_critics(trace_ids)

    # 1. Generate prioritas COHERENCE
    generate_sample_for_lang(df_all, critics_data, "Sistem Bahasa Inggris", "Create an", "en", priority="coherence")
    generate_sample_for_lang(df_all, critics_data, "Sistem Bahasa Indonesia", "Buat cerita", "id", priority="coherence")

    # 2. Generate prioritas FAITHFULNESS
    generate_sample_for_lang(df_all, critics_data, "Sistem Bahasa Inggris", "Create an", "en", priority="faithfulness")
    generate_sample_for_lang(df_all, critics_data, "Sistem Bahasa Indonesia", "Buat cerita", "id", priority="faithfulness")
if __name__ == '__main__':
    generate_sample_md()
