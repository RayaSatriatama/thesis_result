"""
MiniCheck Classifier Wrapper

Direct wrapper untuk model Bespoke-MiniCheck-7B via Ollama.
Melakukan klasifikasi NLI (Natural Language Inference) pada pasangan (premise, hypothesis).

Model mengembalikan skor probabilitas biner:
  - 1.0  : hypothesis didukung oleh premise (consistent/faithful) -> "Yes"
  - 0.0  : hypothesis tidak didukung (hallucinated/unfaithful) -> "No"
"""

from __future__ import annotations

import requests
from typing import List
from loguru import logger

MODEL_NAME = "bespoke-minicheck:7b"


class MiniCheckClassifier:
    """NLI classifier menggunakan Bespoke-MiniCheck-7B via Ollama.

    Menerima pasangan (premise, hypothesis) dan mengembalikan skor 1.0 atau 0.0.

    Args:
        device:     Diabaikan, disediakan untuk kompatibilitas.
        batch_size: Diabaikan, disediakan untuk kompatibilitas.
        ollama_url: URL base untuk Ollama REST API. Default: http://localhost:11434.
    """

    def __init__(
        self,
        device: str = "cpu",
        batch_size: int = 10,
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self._device = device
        self._batch_size = batch_size
        self._ollama_url = ollama_url
        self._model_name = MODEL_NAME

    def classify_single(
        self,
        premise: str,
        hypothesis: str,
    ) -> float:
        """Klasifikasi satu pasangan (premise, hypothesis).

        Returns:
            Skor 1.0 (Yes) atau 0.0 (No).
        """
        prompt = f"Document: {premise} Claim: {hypothesis}"
        url = f"{self._ollama_url}/api/generate"
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip().lower()
            
            if "yes" in output:
                return 1.0
            else:
                return 0.0
        except Exception as exc:
            logger.error(f"[MiniCheck] Gagal klasifikasi: {exc}")
            return 0.0

    def classify_batch(
        self,
        premises: List[str],
        hypotheses: List[str],
    ) -> List[float]:
        """Klasifikasi batch pasangan (premise, hypothesis).

        Args:
            premises:    List konteks sumber (premise).
            hypotheses:  List kalimat yang akan diverifikasi.

        Returns:
            List skor 1.0/0.0 per hypothesis, urutan sesuai input.
        """
        if len(premises) != len(hypotheses):
            raise ValueError(
                f"Jumlah premises ({len(premises)}) != "
                f"jumlah hypotheses ({len(hypotheses)})"
            )

        if not premises:
            return []

        all_scores: List[float] = []
        for p, h in zip(premises, hypotheses):
            all_scores.append(self.classify_single(p, h))

        return all_scores

    def classify_sentences(
        self,
        context: str,
        sentences: List[str],
    ) -> List[float]:
        """Convenience method: verifikasi list kalimat terhadap satu konteks.

        Args:
            context:    Teks konteks sumber utuh (premise).
            sentences:  List kalimat yang akan diverifikasi.

        Returns:
            List skor 1.0/0.0 per kalimat.
        """
        if not sentences:
            return []

        premises = [context] * len(sentences)
        return self.classify_batch(premises, sentences)
