import os
import json
import asyncio
import numpy as np
import pandas as pd
from ragas.dataset_schema import SingleTurnSample
from loguru import logger
import torch

# Monkey-patch torch.nn.Module.__getattr__ to catch "all_tied_weights_keys"
# for compatibility between Vectara HHEMv2 remote code and transformers >= 4.45
_original_getattr = torch.nn.Module.__getattr__

def _patched_getattr(self, name):
    if name == "all_tied_weights_keys":
        val = getattr(self, "_tied_weights_keys", {})
        return val if val is not None else {}
    return _original_getattr(self, name)

torch.nn.Module.__getattr__ = _patched_getattr

import transformers
_original_from_pretrained = transformers.AutoTokenizer.from_pretrained

@classmethod
def _patched_from_pretrained(cls, pretrained_model_name_or_path, *args, **kwargs):
    if pretrained_model_name_or_path == "vectara/hallucination_evaluation_model":
        pretrained_model_name_or_path = "google/flan-t5-base"
    return _original_from_pretrained(pretrained_model_name_or_path, *args, **kwargs)

transformers.AutoTokenizer.from_pretrained = _patched_from_pretrained

import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Kita impor get_langfuse dan segmenter
from workflows.story_agent.integrations.langfuse_client import get_langfuse
from workflows.evaluator.faithfulness.segmenter import segment_all_sentences

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    logger.error("Paket 'sentence-transformers' tidak ditemukan. Harap install dengan: uv pip install sentence-transformers")
    sys.exit(1)

async def main():
    logger.info("Memulai kalibrasi/testing dataset WikiEval dengan Vectara HHEM-2.1-Open...")
    
    # Inisialisasi Langfuse
    langfuse = get_langfuse()
    logger.info("Klien Langfuse diinisialisasi. Data evaluasi akan dikirim ke Langfuse.")
    
    # 1. Inisialisasi model HHEM 2.1
    # Menggunakan CrossEncoder dari sentence-transformers untuk model HHEM
    logger.info("Memuat model vectara/hallucination_evaluation_model... (ini mungkin membutuhkan waktu)")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    hhem_model = CrossEncoder('vectara/hallucination_evaluation_model', device=device, trust_remote_code=True)
    
    # manual weight tie to fix transformers bug
    if hasattr(hhem_model.model, 't5') and hasattr(hhem_model.model.t5, 'transformer'):
        hhem_model.model.t5.transformer.encoder.embed_tokens.weight = hhem_model.model.t5.transformer.shared.weight
    
    def evaluate_hhem(premise: str, text: str) -> float:
        """Evaluasi teks utuh menggunakan segmentasi tingkat kalimat lalu rata-rata HHEM score"""
        segments = segment_all_sentences(text)
        if not segments:
            return 0.0
            
        statements = [seg.text for seg in segments]
        pairs = [(premise, stmt) for stmt in statements]
        
        # Prediksi cross-encoder untuk setiap kalimat
        scores = hhem_model.predict(pairs, apply_softmax=True)
        
        # Konversi ke float biasa dan rata-rata
        if isinstance(scores, (np.ndarray, list)):
            scores = np.array(scores)
            if scores.ndim == 2 and scores.shape[1] == 2:
                probs = scores[:, 1]
            else:
                probs = scores
            avg_score = float(np.mean(probs))
        else:
            avg_score = float(scores)
            
        return avg_score
    
    # 2. Muat dataset
    dataset_path = PROJECT_ROOT.parent / "dataset" / "wikiEval_all.json"
    df = pd.read_json(dataset_path, lines=True)
    
    logger.info(f"Berhasil memuat {len(df)} baris data WikiEval.")
    
    correct_predictions = 0
    total_pairs = len(df)
    results_data = []

    for idx, row in df.iterrows():
        context = "\n".join(row['context_v1']) if isinstance(row['context_v1'], list) else str(row['context_v1'])
        answer_a = row['answer']
        answer_b = row['ungrounded_answer']
        
        # Buat Trace di Langfuse (namai beda untuk HHEM)
        with langfuse.trace(
            name="WikiEval_Faithfulness_Calibration_HHEM",
            input_data={
                "question": row['question'],
                "context": context
            },
            metadata={"idx": idx, "dataset": "WikiEval", "model": "HHEM-2.1"}
        ) as trace:
            
            # --- Evaluasi Jawaban A (Grounded) ---
            langfuse.log_generation(
                name="Grounded_Answer_HHEM",
                model="vectara/hallucination_evaluation_model",
                input_text=row['question'],
                output_text=answer_a,
                metadata={"type": "Grounded"}
            )
            
            score_a = evaluate_hhem(context, answer_a)
            score_a = 0.0 if np.isnan(score_a) else score_a
            
            trace.score(
                name="faithfulness_grounded",
                value=score_a,
                comment="Grounded Answer Score (HHEM)"
            )
            
            # --- Evaluasi Jawaban B (Ungrounded) ---
            langfuse.log_generation(
                name="Ungrounded_Answer_HHEM",
                model="vectara/hallucination_evaluation_model",
                input_text=row['question'],
                output_text=answer_b,
                metadata={"type": "Ungrounded"}
            )
            
            score_b = evaluate_hhem(context, answer_b)
            score_b = 0.0 if np.isnan(score_b) else score_b
            
            trace.score(
                name="faithfulness_ungrounded",
                value=score_b,
                comment="Ungrounded Answer Score (HHEM)"
            )
            
            # --- Cek Preferensi Manusia ---
            if score_a > score_b:
                correct_predictions += 1
                preference_match = 1.0
            elif score_a == score_b:
                correct_predictions += 0.5
                preference_match = 0.5
            else:
                preference_match = 0.0
                
            trace.score(
                name="human_preference_agreement",
                value=preference_match,
                comment="1.0 jika Score A > Score B (Sesuai preferensi manusia)"
            )
            
            results_data.append({
                "idx": idx,
                "score_a": score_a,
                "score_b": score_b,
                "correct": preference_match > 0.0
            })
            
            logger.info(f"[{idx+1}/{total_pairs}] Score A (Grounded): {score_a:.2f} | Score B (Ungrounded): {score_b:.2f} | Match: {preference_match}")

    # Simpan dataset hasil akhir secara lokal
    output_df = pd.DataFrame(results_data)
    output_csv = PROJECT_ROOT / "scripts" / "calibration" / "wikieval_results_hhem.csv"
    output_df.to_csv(output_csv, index=False)
    logger.info(f"Hasil evaluasi lokal HHEM disimpan di {output_csv}")
    
    langfuse.flush()

    agreement_rate = (correct_predictions / total_pairs) * 100
    
    print("\n" + "="*50)
    print("HASIL PENGUJIAN WIKIEVAL DENGAN VECTARA HHEM-2.1-OPEN")
    print("="*50)
    print(f"Total Pasangan Dievaluasi : {total_pairs}")
    print(f"Threshold (tau)           : Belum dilakukan sweep")
    print(f"Akurasi Keselarasan       : {agreement_rate:.2f}%")
    print("Data terkirim ke Langfuse dengan nama trace 'WikiEval_Faithfulness_Calibration_HHEM'.")
    print("="*50)
    
if __name__ == "__main__":
    asyncio.run(main())
