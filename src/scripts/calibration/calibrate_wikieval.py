import os
import json
import asyncio
import numpy as np
import pandas as pd
from ragas.dataset_schema import SingleTurnSample
from loguru import logger

import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from workflows.evaluator.faithfulness.ragas_metric import FaithfulnessWithMiniCheck
from workflows.story_agent.integrations.langfuse_client import get_langfuse

async def main():
    logger.info("Memulai kalibrasi/testing dataset WikiEval dengan FaithfulnessWithMiniCheck (Ollama)...")
    
    # Inisialisasi Langfuse
    langfuse = get_langfuse()
    logger.info("Klien Langfuse diinisialisasi. Data evaluasi akan dikirim ke Langfuse.")
    
    # 1. Inisialisasi metrik
    metric = FaithfulnessWithMiniCheck()
    
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
        
        # Buat Trace di Langfuse (gunakan context manager)
        with langfuse.trace(
            name="WikiEval_Faithfulness_Calibration",
            input_data={
                "question": row['question'],
                "context": context
            },
            metadata={"idx": idx, "dataset": "WikiEval"}
        ) as trace:
            
            # --- Evaluasi Jawaban A (Grounded) ---
            sample_a = SingleTurnSample(
                user_input=row['question'],
                response=answer_a,
                retrieved_contexts=[context]
            )
            
            langfuse.log_generation(
                name="Grounded_Answer",
                model="bespoke-minicheck:7b",
                input_text=row['question'],
                output_text=answer_a,
                metadata={"type": "Grounded"}
            )
            
            score_a = await metric._single_turn_ascore(sample_a, callbacks=None)
            score_a = 0.0 if np.isnan(score_a) else score_a
            
            # Log skor langsung ke trace level
            trace.score(
                name="faithfulness_grounded",
                value=score_a,
                comment="Grounded Answer Score"
            )
            
            # --- Evaluasi Jawaban B (Ungrounded) ---
            sample_b = SingleTurnSample(
                user_input=row['question'],
                response=answer_b,
                retrieved_contexts=[context]
            )
            
            langfuse.log_generation(
                name="Ungrounded_Answer",
                model="bespoke-minicheck:7b",
                input_text=row['question'],
                output_text=answer_b,
                metadata={"type": "Ungrounded"}
            )
            
            score_b = await metric._single_turn_ascore(sample_b, callbacks=None)
            score_b = 0.0 if np.isnan(score_b) else score_b
            
            # Log skor langsung ke trace level
            trace.score(
                name="faithfulness_ungrounded",
                value=score_b,
                comment="Ungrounded Answer Score"
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
                
            # Log status keselarasan ke Langfuse di tingkat Trace
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
    output_csv = PROJECT_ROOT / "scripts" / "calibration" / "wikieval_results.csv"
    output_df.to_csv(output_csv, index=False)
    logger.info(f"Hasil evaluasi lokal disimpan di {output_csv}")
    
    # Flush Langfuse untuk memastikan semua log terkirim
    langfuse.flush()

    agreement_rate = (correct_predictions / total_pairs) * 100
    
    print("\n" + "="*50)
    print("HASIL PENGUJIAN WIKIEVAL DENGAN BESPOKE-MINICHECK-7B")
    print("="*50)
    print(f"Total Pasangan Dievaluasi : {total_pairs}")
    print(f"Threshold (tau)           : N/A (Hard Labels dari Ollama)")
    print(f"Akurasi Keselarasan       : {agreement_rate:.2f}%")
    print("Data terkirim ke Langfuse.")
    print("="*50)
    
if __name__ == "__main__":
    asyncio.run(main())
