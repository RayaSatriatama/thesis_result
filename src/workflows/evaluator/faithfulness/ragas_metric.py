"""
Custom RAGAS Metric: FaithfulnessWithMiniCheck

Mengintegrasikan Bespoke-MiniCheck-7B (via Ollama) ke dalam ekosistem Ragas.
Metrik ini menggantikan proses ekstraksi atomic-claims berbasis LLM yang ada di Ragas bawaan,
dan langsung menggunakan segmentasi kalimat (STORYSUMM approach) sebelum memverifikasi
kebenarannya menggunakan classifier NLI (Bespoke-MiniCheck-7B).
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

import numpy as np

try:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics.base import MetricOutputType, MetricType, SingleTurnMetric
except ImportError as exc:
    raise ImportError(
        "Paket 'ragas' belum terinstal. Jalankan: uv pip install ragas"
    ) from exc

from .minicheck_classifier import MiniCheckClassifier
from .segmenter import segment_all_sentences


@dataclass
class FaithfulnessWithMiniCheck(SingleTurnMetric):
    """
    RAGAS Custom Metric untuk Faithfulness menggunakan Bespoke-MiniCheck-7B via Ollama.
    Menghindari ekstraksi LLM (atomic claims) dan menggunakan segmentasi kalimat (STORYSUMM).
    """

    name: str = "faithfulness_minicheck"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {
            MetricType.SINGLE_TURN: {
                "user_input",
                "response",
                "retrieved_contexts",
            }
        }
    )
    output_type: t.Optional[MetricOutputType] = MetricOutputType.CONTINUOUS
    ollama_url: str = "http://localhost:11434"

    # Digunakan untuk lazy initialization
    _classifier: t.Optional[MiniCheckClassifier] = field(init=False, default=None, repr=False)

    def __post_init__(self):
        super().__post_init__()
        # Inisialisasi wrapper classifier MiniCheck
        self._classifier = MiniCheckClassifier(ollama_url=self.ollama_url)

    def init(self, run_config: t.Any) -> None:
        """
        Inisialisasi metrik jika dibutuhkan oleh Ragas.
        """
        pass

    async def _single_turn_ascore(self, sample: SingleTurnSample, callbacks: t.Any) -> float:
        """
        Antarmuka utama untuk SingleTurnMetric di RAGAS.
        """
        row = sample.to_dict()
        return await self._ascore(row, callbacks)

    async def _ascore(self, row: t.Dict, callbacks: t.Any) -> float:
        """
        Evaluasi faithfulness untuk satu baris (row) data.
        1. Segmentasi kalimat dari response.
        2. Verifikasi dengan MiniCheck terhadap retrieved_contexts.
        """
        response = row.get("response", "")
        retrieved_contexts = row.get("retrieved_contexts", [])

        if not response or not retrieved_contexts:
            return np.nan

        # Tahap 1: Segmentasi level kalimat (tanpa LLM, lebih cepat & hemat)
        segments = segment_all_sentences(response)
        if not segments:
            return np.nan

        statements = [seg.text for seg in segments]
        premise = "\n\n---\n\n".join(retrieved_contexts)

        # Tahap 2: Verifikasi via MiniCheck
        # classify_sentences memproses secara sequential, tapi sudah optimal untuk local inference
        scores = self._classifier.classify_sentences(premise, statements)

        if not scores:
            return np.nan

        # Aggregation: Rata-rata dari skor seluruh kalimat (1.0 atau 0.0 per kalimat)
        return float(sum(scores) / len(scores))
