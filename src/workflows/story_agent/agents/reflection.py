"""
Reflection Module - Implementasi Arsitektur Reflexion (Shinn et al., 2023)

Menyediakan kapabilitas cross-episode learning melalui:
- ReflectionGenerator : Menganalisis hasil sesi dan menyimpan catatan refleksi ke SQLite
- ReflectionRetriever : Mengambil catatan refleksi relevan sebelum WriterAgent mulai menulis
"""

import json
import os
import sqlite3
from typing import List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from ..state import StoryState
from providers.llm_factory import get_llm_for_agent

# ---------------------------------------------------------------------------
# Konstanta path database
# ---------------------------------------------------------------------------
_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_AGENTS_DIR, "..", "..", "..", ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "Eval_Data", "reflections.db")

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    trace_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Konteks cerita
    theme TEXT NOT NULL,
    language TEXT NOT NULL,
    topic_category TEXT,

    -- Metrik evaluasi
    faithfulness_fables REAL,
    faithfulness_ragas REAL,
    geval_avg REAL,
    revision_count INTEGER,
    quality_score REAL,

    -- Catatan refleksi (dihasilkan oleh LLM)
    reflection_text TEXT NOT NULL,
    action_items TEXT,
    failure_patterns TEXT,

    -- Embedding untuk pencarian semantik (opsional, tidak digunakan saat ini)
    theme_embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_reflections_topic ON reflections(topic_category);
CREATE INDEX IF NOT EXISTS idx_reflections_language ON reflections(language);
"""

_MAX_REFLECTIONS_PER_CATEGORY = 100


# ---------------------------------------------------------------------------
# Pydantic schema untuk output terstruktur LLM
# ---------------------------------------------------------------------------

class ReflectionNote(BaseModel):
    """Structured reflection note generated after story completion."""

    strengths: List[str] = Field(
        ..., description="Aspek yang berhasil dilakukan dengan baik"
    )
    weaknesses: List[str] = Field(
        ..., description="Aspek yang memerlukan perbaikan"
    )
    failure_patterns: List[str] = Field(
        ..., description="Pola kegagalan yang teridentifikasi"
    )
    action_items: List[str] = Field(
        ..., description="Langkah spesifik untuk meningkatkan kualitas "
                         "pada cerita bertema serupa di masa depan"
    )
    topic_category: str = Field(
        ..., description=(
            "Kategori topik: science, history, culture, geography, "
            "biology, mathematics, language, religion, social, technology, other"
        )
    )
    reflection_summary: str = Field(
        ..., description="Ringkasan refleksi dalam 2-3 kalimat"
    )


# ---------------------------------------------------------------------------
# ReflectionGenerator
# ---------------------------------------------------------------------------

class ReflectionGenerator:
    """
    Menghasilkan dan menyimpan catatan refleksi setelah sesi cerita selesai.

    Dipanggil sebagai node LangGraph setelah node 'finalize'.
    """

    def __init__(self, model_name: Optional[str] = None, **kwargs):
        # kwargs menyerap argumen legacy (credentials, project) yang tidak digunakan
        self.llm = get_llm_for_agent("reflection", model_name=model_name)
        self.structured_llm = self.llm.with_structured_output(ReflectionNote)
        self.db_path = DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        """Inisialisasi database SQLite dan buat tabel jika belum ada."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_INIT_SQL)
        logger.debug(f"[REFLEKSI::DB] Database siap di {self.db_path}")

    async def generate_and_store(self, state: StoryState) -> dict:
        """
        Analisis hasil akhir cerita dan simpan catatan refleksi ke SQLite.

        Node LangGraph: dipanggil setelah 'finalize', sebelum 'ingest_sources'.
        """
        logger.info("[REFLEKSI::GENERATE] Membuat catatan refleksi dari sesi ini...")

        try:
            context = self._build_reflection_context(state)
            reflection: ReflectionNote = await self.structured_llm.ainvoke(context)
            self._store_reflection(state, reflection)
            logger.success(
                f"[REFLEKSI::GENERATE] Catatan refleksi tersimpan. "
                f"Kategori: {reflection.topic_category} | "
                f"Poin perbaikan: {len(reflection.action_items)}"
            )
            return {"reflection_generated": True}
        except Exception as exc:
            logger.error(f"[REFLEKSI::GENERATE] Gagal membuat catatan refleksi: {exc}")
            return {"reflection_generated": False}

    def _build_reflection_context(self, state: StoryState) -> str:
        """Bangun prompt refleksi dari state akhir sesi."""
        draft_preview = (state.get("draft_content") or "")[:500]
        research_preview = (state.get("research_notes") or "")[:300]

        return (
            "Analisis hasil pembuatan cerita berikut dan buat catatan refleksi yang konstruktif.\n\n"
            f"Tema: {state.get('theme', '')}\n"
            f"Bahasa: {state.get('language', '')}\n"
            f"Jumlah Revisi: {state.get('revision_count', 0)}\n"
            f"Skor Kualitas Akhir: {state.get('quality_score', 0.0)}\n\n"
            f"Umpan Balik Kritik Terakhir:\n{state.get('critique_feedback', 'Tidak ada')}\n\n"
            f"Ringkasan Draf (500 karakter pertama):\n{draft_preview}\n\n"
            f"Catatan Riset (300 karakter pertama):\n{research_preview}\n\n"
            "Berdasarkan informasi di atas, identifikasi:\n"
            "1. Apa yang berhasil dengan baik?\n"
            "2. Apa yang masih lemah?\n"
            "3. Pola kegagalan apa yang perlu diwaspadai?\n"
            "4. Langkah spesifik apa yang harus dilakukan untuk topik serupa di masa depan?\n"
            "5. Tentukan satu kategori topik yang paling tepat untuk cerita ini.\n"
        )

    def _store_reflection(self, state: StoryState, reflection: ReflectionNote) -> None:
        """
        Simpan catatan refleksi ke SQLite. Terapkan kebijakan retensi:
        maksimal _MAX_REFLECTIONS_PER_CATEGORY entri per kategori topik.
        """
        action_items_json = json.dumps(reflection.action_items, ensure_ascii=False)
        failure_patterns_json = json.dumps(reflection.failure_patterns, ensure_ascii=False)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reflections (
                    session_id, trace_id, theme, language, topic_category,
                    revision_count, quality_score,
                    reflection_text, action_items, failure_patterns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.get("session_id", ""),
                    state.get("trace_id", ""),
                    state.get("theme", ""),
                    state.get("language", ""),
                    reflection.topic_category,
                    state.get("revision_count", 0),
                    state.get("quality_score", 0.0),
                    reflection.reflection_summary,
                    action_items_json,
                    failure_patterns_json,
                ),
            )

            # Kebijakan retensi: hapus entri lama jika melebihi batas per kategori
            conn.execute(
                """
                DELETE FROM reflections
                WHERE topic_category = ?
                  AND id NOT IN (
                      SELECT id FROM reflections
                      WHERE topic_category = ?
                      ORDER BY timestamp DESC
                      LIMIT ?
                  )
                """,
                (reflection.topic_category, reflection.topic_category, _MAX_REFLECTIONS_PER_CATEGORY),
            )


# ---------------------------------------------------------------------------
# ReflectionRetriever
# ---------------------------------------------------------------------------

class ReflectionRetriever:
    """
    Mengambil catatan refleksi relevan sebelum WriterAgent mulai menulis.

    Dipanggil sebagai node LangGraph sebelum 'dispatch_to_writers'.
    """

    def __init__(self, **kwargs):
        # kwargs menyerap argumen legacy untuk konsistensi antarmuka
        self.db_path = DB_PATH

    async def retrieve(self, state: StoryState) -> dict:
        """
        Ambil refleksi relevan berdasarkan kesamaan tema/kategori topik dan bahasa.

        Node LangGraph: dipanggil setelah 'research', sebelum 'dispatch_to_writers'.
        """
        theme = state.get("theme", "")
        language = state.get("language", "")

        if not os.path.exists(self.db_path):
            logger.debug("[REFLEKSI::RETRIEVE] Database belum ada, lewati pengambilan refleksi.")
            return {"past_reflections": ""}

        reflections = self._query_similar_reflections(theme, language, limit=3)

        if reflections:
            reflection_prompt = self._format_for_writer(reflections)
            logger.info(
                f"[REFLEKSI::RETRIEVE] Ditemukan {len(reflections)} catatan refleksi relevan "
                f"untuk tema '{theme}' (bahasa: {language})"
            )
            return {"past_reflections": reflection_prompt}

        logger.debug(
            f"[REFLEKSI::RETRIEVE] Tidak ada refleksi relevan untuk tema '{theme}' "
            f"(bahasa: {language})"
        )
        return {"past_reflections": ""}

    def _query_similar_reflections(
        self, theme: str, language: str, limit: int = 3
    ) -> List[dict]:
        """
        Query refleksi berdasarkan bahasa dan, jika tersedia, kategori topik.

        Strategi pencarian (urutan prioritas):
        1. Cocokkan bahasa + kategori topik yang relevan berdasarkan kata kunci tema
        2. Jika tidak ada hasil, ambil refleksi terbaru berdasarkan bahasa saja
        """
        rows = []

        # Ekstrak kata kunci tema untuk menebak kategori
        theme_lower = theme.lower()
        category_hints = self._guess_category_from_theme(theme_lower)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                if category_hints:
                    placeholders = ",".join("?" * len(category_hints))
                    cursor = conn.execute(
                        f"""
                        SELECT theme, language, topic_category,
                               reflection_text, action_items, failure_patterns,
                               quality_score, revision_count, timestamp
                        FROM reflections
                        WHERE language = ?
                          AND topic_category IN ({placeholders})
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        [language, *category_hints, limit],
                    )
                    rows = cursor.fetchall()

                # Fallback: ambil berdasarkan bahasa saja
                if not rows:
                    cursor = conn.execute(
                        """
                        SELECT theme, language, topic_category,
                               reflection_text, action_items, failure_patterns,
                               quality_score, revision_count, timestamp
                        FROM reflections
                        WHERE language = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        (language, limit),
                    )
                    rows = cursor.fetchall()

        except sqlite3.Error as exc:
            logger.warning(f"[REFLEKSI::RETRIEVE] Gagal query SQLite: {exc}")
            return []

        result = []
        for row in rows:
            try:
                action_items = json.loads(row["action_items"] or "[]")
                failure_patterns = json.loads(row["failure_patterns"] or "[]")
            except (json.JSONDecodeError, TypeError):
                action_items = []
                failure_patterns = []

            result.append({
                "theme": row["theme"],
                "topic_category": row["topic_category"],
                "reflection_text": row["reflection_text"],
                "action_items": action_items,
                "failure_patterns": failure_patterns,
                "quality_score": row["quality_score"],
            })

        return result

    def _guess_category_from_theme(self, theme_lower: str) -> List[str]:
        """
        Tebak kategori topik berdasarkan kata kunci dalam tema.

        Mengembalikan daftar kategori yang kemungkinan relevan.
        """
        keyword_to_category = {
            "science": ["sains", "ilmu", "eksperimen", "kimia", "fisika", "listrik", "energi"],
            "biology": ["biologi", "hewan", "tumbuhan", "ekosistem", "alam", "lingkungan", "habitat"],
            "history": ["sejarah", "pahlawan", "perjuangan", "perang", "kerajaan", "zaman"],
            "culture": ["budaya", "tradisi", "adat", "suku", "tari", "seni", "wayang"],
            "geography": ["geografi", "peta", "benua", "gunung", "sungai", "laut", "negara"],
            "mathematics": ["matematika", "angka", "hitung", "bilangan", "geometri"],
            "technology": ["teknologi", "komputer", "robot", "internet", "digital", "kecerdasan buatan"],
            "social": ["sosial", "masyarakat", "keluarga", "persahabatan", "tolong", "gotong"],
            "language": ["bahasa", "kata", "puisi", "sastra", "cerita", "dongeng"],
            "religion": ["agama", "ibadah", "tuhan", "doa", "moral", "akhlak"],
        }

        matched = []
        for category, keywords in keyword_to_category.items():
            if any(kw in theme_lower for kw in keywords):
                matched.append(category)

        return matched

    def _format_for_writer(self, reflections: List[dict]) -> str:
        """Format catatan refleksi menjadi instruksi yang dapat diinjeksikan ke prompt WriterAgent."""
        lines = ["=== CATATAN REFLEKSI DARI SESI SEBELUMNYA ==="]
        lines.append(
            "Perhatikan catatan berikut untuk menghindari kesalahan serupa "
            "pada cerita saat ini:\n"
        )

        for i, ref in enumerate(reflections, 1):
            lines.append(f"--- Refleksi #{i} (Tema: {ref['theme']}, Kategori: {ref['topic_category']}) ---")
            lines.append(f"Ringkasan: {ref['reflection_text']}")

            if ref["failure_patterns"]:
                patterns_str = "; ".join(ref["failure_patterns"][:3])
                lines.append(f"Pola kegagalan yang perlu dihindari: {patterns_str}")

            if ref["action_items"]:
                items_str = "; ".join(ref["action_items"][:3])
                lines.append(f"Langkah perbaikan yang disarankan: {items_str}")

            lines.append("")

        lines.append("Gunakan catatan di atas sebagai panduan untuk menghasilkan cerita yang lebih baik.")
        return "\n".join(lines)
