import os
import sys
import json

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(base_dir, 'Streamlit'))

from lib.faithfulness_metrics import load_ten_story_traces_df, load_trace_claims
from sampling_expert import get_latest_trace_df

def overwrite_faithfulness_files():
    tops = load_ten_story_traces_df()
    trace_claims = load_trace_claims(tops['id'].tolist())
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_stories_en = os.path.join(script_dir, "expert_judgement_stories_faithfulness_en.md")
    out_evals_en = os.path.join(script_dir, "expert_judgement_evals_faithfulness_en.md")
    out_stories_id = os.path.join(script_dir, "expert_judgement_stories_faithfulness_id.md")
    out_evals_id = os.path.join(script_dir, "expert_judgement_evals_faithfulness_id.md")
    
    def write_files(lang, tops_lang, out_stories, out_evals):
        with open(out_stories, 'w', encoding='utf-8') as f_story, open(out_evals, 'w', encoding='utf-8') as f_eval:
            lang_name = "Sistem Bahasa Inggris" if lang == "en" else "Sistem Bahasa Indonesia"
            f_story.write(f"# Sampel Cerita ({lang_name} - FAITHFULNESS - 5 Cerita)\n\n")
            f_eval.write(f"# Evaluasi Sampel Cerita ({lang_name} - FAITHFULNESS - 5 Cerita)\n")
            f_eval.write(f"Metode: **Disproportional Stratified Sampling** (Sync with Streamlit Dashboard)\n\n")
            
            for i, row in tops_lang.iterrows():
                trace_id = row['id']
                coh_score = row.get('geval_coherence_normalized', 0.0)
                ragas_score = row.get('ragas_standard_faithfulness', 0.0)
                fables_score = row.get('fables_faithfulness', 0.0)
                kategori = row.get('kategori', 'UNKNOWN')
                pertanyaan = row.get('input', 'N/A')
                raw_cerita = row.get('output', 'N/A')
                
                judul_cerita = "Tanpa Judul"
                cerita_final = str(raw_cerita)
                
                if isinstance(raw_cerita, str):
                    try:
                        import ast
                        parsed_str = ast.literal_eval(raw_cerita) if raw_cerita.strip().startswith(('"',"'")) else raw_cerita
                        parsed_dict = json.loads(parsed_str) if isinstance(parsed_str, str) else parsed_str
                        if isinstance(parsed_dict, str):
                            parsed_dict = json.loads(parsed_dict)
                        if isinstance(parsed_dict, dict):
                            judul_cerita = parsed_dict.get('draft_title', 'Tanpa Judul')
                            cerita_final = parsed_dict.get('final_story', cerita_final)
                    except:
                        pass
                
                counter = i + 1
                f_story.write(f"## Sampel {counter}: {kategori}\n")
                f_story.write(f"### Judul: {judul_cerita}\n\n")
                f_story.write(f"**Prompt / Input:**\n> {pertanyaan}\n\n")
                f_story.write(f"**Cerita:**\n\n{cerita_final}\n\n")
                f_story.write("---\n\n")
                
                f_eval.write(f"## Evaluasi Sampel {counter}: {kategori}\n")
                f_eval.write(f"### Judul: {judul_cerita}\n\n")
                f_eval.write(f"- **Koherensi (G-Eval Norm):** `{coh_score:.3f}`\n")
                f_eval.write(f"- **Faithfulness (RAGAS):** `{ragas_score:.3f}`\n")
                f_eval.write(f"- **Faithfulness (FABLES):** `{fables_score:.3f}`\n\n")
                
                claims = trace_claims.get(trace_id, [])
                if claims:
                    f_eval.write(f"### Ekstraksi Klaim dan Verifikasi (RAGAS & FABLES)\n")
                    f_eval.write(f"*(Aturan: FABLES mengabaikan CANT_VERIFY, sedangkan RAGAS menganggap CANT_VERIFY sebagai UNFAITHFUL)*\n\n")
                    for idx_c, c in enumerate(claims, 1):
                        verdict = c.get('verdict', 'UNKNOWN')
                        fables_label = verdict
                        ragas_label = "UNFAITHFUL" if verdict == "CANT_VERIFY" else verdict
                        f_eval.write(f"**{idx_c}. Klaim:** {c.get('claim', '')}\n")
                        f_eval.write(f"- FABLES: `{fables_label}`\n")
                        f_eval.write(f"- RAGAS : `{ragas_label}`\n\n")
                f_eval.write("---\n\n")
    
    tops_en = tops[tops['lang'] == 'en'].reset_index(drop=True)
    tops_id = tops[tops['lang'] == 'id'].reset_index(drop=True)
    
    write_files("en", tops_en, out_stories_en, out_evals_en)
    write_files("id", tops_id, out_stories_id, out_evals_id)
    print("Files successfully overwritten to match 117 claims!")

if __name__ == '__main__':
    overwrite_faithfulness_files()
