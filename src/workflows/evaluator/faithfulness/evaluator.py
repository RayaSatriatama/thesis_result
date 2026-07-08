"""
Faithfulness Evaluator - Sentence-Level STORYSUMM + HHEM-2.1-Open

Mengukur seberapa setia (faithful) output yang dihasilkan agent terhadap
konteks / sumber referensi, menggunakan pendekatan STORYSUMM:

  1. Segmentasi kalimat utuh (bukan atomic claims) -- evaluasi pada tingkat
     kalimat sudah memadai untuk ketelitian tinggi dan menjaga keutuhan
     konteks alur cerita.
  2. Konteks sumber disajikan secara utuh berdampingan dengan kalimat yang
     dievaluasi (STORYSUMM approach).
  3. Model HHEM-2.1-Open (T5 classifier) memverifikasi setiap kalimat
     terhadap konteks sebagai pasangan NLI (premise, hypothesis).

Dua mode evaluasi:
  - full_sentence  : evaluasi semua kalimat dalam response
  - citation_only  : evaluasi hanya kalimat yang mengandung citation marker

Referensi:
  - STORYSUMM (sentence-level faithfulness evaluation)
  - Vectara HHEM-2.1-Open: https://huggingface.co/vectara/hallucination_evaluation_model

Cara pakai:
    from workflows.evaluator.faithfulness import FaithfulnessEvaluator

    evaluator = FaithfulnessEvaluator(
        mode=EvaluationMode.FULL_SENTENCE,
        device="cpu",
        batch_size=10,
    )

    result = await evaluator.evaluate(
        user_input="Apa itu tata surya?",
        response="Tata surya terdiri dari Matahari dan 8 planet [1]...",
        retrieved_contexts=["Tata surya adalah sistem bintang...", "..."],
    )
    print(result.score)            # float 0-1
    print(result.passed)           # True/False (>= threshold)
    print(result.sentences)        # detail per kalimat
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from loguru import logger

from .minicheck_classifier import MiniCheckClassifier
from .segmenter import (
    SentenceSegment,
    segment_all_sentences,
    segment_citation_sentences,
)

# ---------------------------------------------------------------------------
# Enums & Data Structures
# ---------------------------------------------------------------------------


class EvaluationMode(str, Enum):
    """Mode evaluasi faithfulness."""
    FULL_SENTENCE = "full_sentence"
    CITATION_ONLY = "citation_only"


@dataclass
class SentenceResult:
    """Hasil evaluasi per kalimat."""

    index: int
    """Posisi kalimat dalam teks asli (0-indexed)."""

    text: str
    """Kalimat utuh."""

    score: float
    """Skor MiniCheck 1.0 (Yes) atau 0.0 (No)."""

    supported: bool
    """True jika score >= threshold."""

    has_citation: bool
    """True jika kalimat mengandung citation marker."""

    citation_ids: List[int] = field(default_factory=list)
    """Daftar ID citation yang ditemukan."""


@dataclass
class FaithfulnessResult:
    """Hasil evaluasi faithfulness untuk satu sample."""

    score: float
    """Rata-rata skor MiniCheck semua kalimat yang dievaluasi (0.0--1.0)."""

    passed: bool
    """True jika score >= threshold."""

    threshold: float
    """Ambang batas yang digunakan."""

    mode: str
    """Mode evaluasi: 'full_sentence' atau 'citation_only'."""

    num_sentences: int
    """Total kalimat yang dievaluasi."""

    num_supported: int
    """Jumlah kalimat dengan skor >= threshold."""

    num_unsupported: int
    """Jumlah kalimat dengan skor < threshold."""

    sentences: List[SentenceResult] = field(default_factory=list)
    """Detail hasil per kalimat."""

    user_input: str = ""
    retrieved_contexts: List[str] = field(default_factory=list)
    response: str = ""

    error: Optional[str] = None
    """Pesan error jika terjadi kegagalan."""


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class FaithfulnessEvaluator:
    """
    Sentence-level faithfulness evaluator menggunakan STORYSUMM approach
    dengan Bespoke-MiniCheck-7B (via Ollama) sebagai NLI classifier.

    Args:
        mode:       Mode evaluasi. Default: FULL_SENTENCE.
        device:     Perangkat untuk model (Diabaikan, untuk kompatibilitas).
        batch_size: Ukuran batch saat inferensi (Diabaikan, untuk kompatibilitas).
        threshold:  Ambang batas skor per kalimat untuk atribut `supported`
                    dan skor agregat untuk `passed`. Default: 0.5.
    """

    def __init__(
        self,
        mode: EvaluationMode = EvaluationMode.FULL_SENTENCE,
        device: str = "cpu",
        batch_size: int = 10,
        threshold: float = 0.5,
    ) -> None:
        self._mode = mode
        self._device = device
        self._batch_size = batch_size
        self._threshold = threshold
        self._classifier: Optional[MiniCheckClassifier] = None  # lazy-load

    def _get_classifier(self) -> MiniCheckClassifier:
        """Inisialisasi MiniCheckClassifier sekali (lazy)."""
        if self._classifier is not None:
            return self._classifier

        logger.info(
            f"[FAITHFULNESS] Inisialisasi MiniCheckClassifier "
            f"(device={self._device}, batch_size={self._batch_size})"
        )
        self._classifier = MiniCheckClassifier(
            device=self._device,
            batch_size=self._batch_size,
        )
        return self._classifier

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        user_input: str,
        response: str,
        retrieved_contexts: List[str],
    ) -> FaithfulnessResult:
        """
        Evaluasi satu sample secara asinkron.

        Pipeline:
          1. Segmentasi kalimat dari response (sesuai mode)
          2. Join retrieved_contexts menjadi satu premise string utuh
          3. Batch classify semua kalimat terhadap premise via MiniCheck
          4. Agregasi skor per kalimat menjadi FaithfulnessResult

        Args:
            user_input:          Pertanyaan / prompt asli pengguna.
            response:            Teks output yang ingin dievaluasi.
            retrieved_contexts:  Daftar konteks / sumber referensi.

        Returns:
            FaithfulnessResult dengan detail per kalimat.
        """
        try:
            # 1. Segmentasi kalimat
            if self._mode == EvaluationMode.CITATION_ONLY:
                segments = segment_citation_sentences(response)
                logger.info(
                    f"[FAITHFULNESS] Mode citation_only: "
                    f"{len(segments)} kalimat ber-citation ditemukan"
                )
            else:
                segments = segment_all_sentences(response)
                logger.info(
                    f"[FAITHFULNESS] Mode full_sentence: "
                    f"{len(segments)} kalimat tersegmentasi"
                )

            if not segments:
                logger.warning(
                    "[FAITHFULNESS] Tidak ada kalimat yang tersegmentasi, "
                    "mengembalikan skor 0.0."
                )
                return FaithfulnessResult(
                    score=0.0,
                    passed=False,
                    threshold=self._threshold,
                    mode=self._mode.value,
                    num_sentences=0,
                    num_supported=0,
                    num_unsupported=0,
                    sentences=[],
                    user_input=user_input,
                    retrieved_contexts=retrieved_contexts,
                    response=response,
                )

            # 2. Join konteks menjadi satu premise utuh (STORYSUMM approach)
            context_premise = "\n\n---\n\n".join(retrieved_contexts)

            # 3. Batch classify via MiniCheck
            classifier = self._get_classifier()
            sentence_texts = [seg.text for seg in segments]

            # Run HHEM inference in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(
                None,
                classifier.classify_sentences,
                context_premise,
                sentence_texts,
            )

            # 4. Agregasi hasil
            sentence_results: List[SentenceResult] = []
            num_supported = 0
            num_unsupported = 0

            for seg, score in zip(segments, scores):
                supported = score >= self._threshold
                if supported:
                    num_supported += 1
                else:
                    num_unsupported += 1

                sentence_results.append(
                    SentenceResult(
                        index=seg.index,
                        text=seg.text,
                        score=round(score, 4),
                        supported=supported,
                        has_citation=seg.has_citation,
                        citation_ids=seg.citation_ids,
                    )
                )

            avg_score = sum(scores) / len(scores) if scores else 0.0
            avg_score = round(avg_score, 4)
            passed = avg_score >= self._threshold

            logger.info(
                f"[FAITHFULNESS] Skor: {avg_score:.4f} | "
                f"Passed: {passed} (threshold={self._threshold}) | "
                f"Supported: {num_supported}/{len(segments)}"
            )

            return FaithfulnessResult(
                score=avg_score,
                passed=passed,
                threshold=self._threshold,
                mode=self._mode.value,
                num_sentences=len(segments),
                num_supported=num_supported,
                num_unsupported=num_unsupported,
                sentences=sentence_results,
                user_input=user_input,
                retrieved_contexts=retrieved_contexts,
                response=response,
            )

        except Exception as exc:
            logger.error(f"[FAITHFULNESS] Gagal mengevaluasi: {exc}")
            return FaithfulnessResult(
                score=0.0,
                passed=False,
                threshold=self._threshold,
                mode=self._mode.value,
                num_sentences=0,
                num_supported=0,
                num_unsupported=0,
                sentences=[],
                user_input=user_input,
                retrieved_contexts=retrieved_contexts,
                response=response,
                error=str(exc),
            )

    @property
    def version(self) -> str:
        """Identifier versi evaluator untuk metadata skor."""
        return "storysumm_minicheck_v1"

    async def evaluate_against_reference(
        self,
        response: str,
        reference: str,
    ) -> FaithfulnessResult:
        """
        Evaluasi faithfulness output terhadap teks referensi ground truth.

        Berbeda dari ``evaluate()``: premise/konteks adalah reference text
        (ground truth), bukan retrieved_contexts dari RAG pipeline.

        Args:
            response:   Teks output yang ingin dievaluasi.
            reference:  Teks referensi ground truth.

        Returns:
            FaithfulnessResult dengan detail per kalimat.
        """
        return await self.evaluate(
            user_input="",
            response=response,
            retrieved_contexts=[reference],
        )

    def evaluate_sync(
        self,
        user_input: str,
        response: str,
        retrieved_contexts: List[str],
    ) -> FaithfulnessResult:
        """
        Versi sinkron dari ``evaluate``.
        Aman dipanggil dari context non-async (skrip, notebook, dsb.).
        """
        return asyncio.run(
            self.evaluate(
                user_input=user_input,
                response=response,
                retrieved_contexts=retrieved_contexts,
            )
        )
