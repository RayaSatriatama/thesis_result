"""
Director Agent (Agen Sutradara) - Generates annotated dialogue script from story.

Converts finished story content into a screenplay-style .md file with JSON
metadata blocks embedded as HTML comments, suitable for TTS and animation systems.

Agent ini membuat skrip dialog/skenario dari cerita yang sudah selesai,
menghasilkan file .md beranotasi di output/{session_id}_script.md.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from loguru import logger

from ..state import StoryState
from settings import StoryConfig, LanguageConfig
from ..prompts import get_registry
from providers.llm_factory import get_llm_for_agent


# === PYDANTIC MODELS FOR STRUCTURED OUTPUT ===

class SceneBlock(BaseModel):
    """Represents a single scene block in the annotated screenplay."""
    scene_type: str = Field(
        description="Tipe blok: 'dialog', 'narasi', atau 'transisi'"
    )
    character: Optional[str] = Field(
        default=None,
        description="Nama karakter yang berbicara (hanya untuk tipe 'dialog')"
    )
    text: str = Field(
        description="Teks dialog atau narasi yang dibacakan/ditampilkan"
    )
    time_hint: Optional[str] = Field(
        default=None,
        description="Petunjuk waktu/suasana scene, misal: 'pagi', 'malam', 'tegang'"
    )
    narrator_text: Optional[str] = Field(
        default=None,
        description="Catatan narasi/konteks audio pendamping (opsional)"
    )
    scene_setting: Optional[str] = Field(
        default=None,
        description="Lokasi/latar scene, misal: 'perpustakaan', 'taman', 'ruang kelas'"
    )


class ScriptOutput(BaseModel):
    """Complete annotated screenplay output."""
    title: str = Field(description="Judul skrip/cerita")
    scene_count: int = Field(description="Jumlah total blok scene")
    scenes: List[SceneBlock] = Field(description="Daftar blok scene secara berurutan")


# Import Langfuse for observability
try:
    from ..integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None


def _is_serverless_runtime() -> bool:
    return bool(
        os.getenv("VERCEL")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("LAMBDA_TASK_ROOT")
    )


def _script_output_dir() -> Path:
    if _is_serverless_runtime():
        return Path(tempfile.gettempdir()) / "skripsi" / "output"
    return Path("output")


class DirectorAgent:
    """
    Agen Sutradara — mengonversi cerita menjadi skrip dialog beranotasi.

    Membaca draft cerita yang sudah selesai lalu menghasilkan file .md dengan
    blok scene beranotasi (format JSON dalam HTML comment) untuk keperluan
    text-to-speech dan sistem animasi.

    Output: file .md tersimpan di output/{session_id}_script.md
    """

    def __init__(self, model_name: Optional[str] = None, credentials=None, project=None):
        """
        Initialize DirectorAgent.

        Args:
            model_name: Override model name
            credentials: Google service account credentials (reserved for API compat)
            project: Google Cloud project ID (reserved for API compat)
        """
        self.llm = get_llm_for_agent("director", model_name=model_name)
        self.structured_llm = self.llm.with_structured_output(ScriptOutput)
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None

        logger.info("[SUTRADARA::PENGATURAN] Saya sudah siap, LLM terinstansiasi. Menunggu cerita untuk diubah menjadi skrip dialog.")

    async def direct(self, state: StoryState) -> Dict:
        """
        Main method — menghasilkan skrip dialog dari cerita yang ada.

        Dipanggil oleh LangGraph workflow sebagai production writer paralel.
        Melewati proses jika ENABLE_DIRECTOR=false atau 'director' tidak ada
        di active_writers.

        Args:
            state: Current StoryState berisi draft cerita yang sudah selesai

        Returns:
            Dict berisi draft_script, script_file_path, script_scene_count;
            atau {} jika agent di-skip.
        """
        # Skip guard: feature flag
        if not StoryConfig.ENABLE_DIRECTOR:
            logger.info("[SUTRADARA::LEWATI] Fitur sutradara dinonaktifkan (ENABLE_DIRECTOR=false), saya tidak akan membuat skrip dialog untuk sesi ini.")
            return {}

        # Skip guard: not in active_writers
        active_writers = state.get("active_writers", ["text"])
        if "director" not in active_writers:
            logger.info("[SUTRADARA::LEWATI] Saya tidak ditugaskan dalam tim penulis aktif kali ini, melewati pembuatan skrip dialog.")
            return {}

        start_time = time.time()
        session_id = state.get("session_id", "unknown")
        language = state.get("language", LanguageConfig.get_display_name())

        logger.info(f"[SUTRADARA::MULAI] Saya mulai mengerjakan skrip dialog, sesi: {session_id}, bahasa: {language}, panjang cerita: {len(state.get('final_story') or state.get('draft_content', ''))} karakter.")

        span_id = None
        if self.langfuse:
            span_id = self.langfuse.start_span(
                name="director_agent",
                input_data={"session_id": session_id, "language": language},
                metadata={"agent": "director"}
            )

        try:
            # Read story content from state (final approved story preferred)
            story_content = state.get("final_story") or state.get("draft_content", "")
            characters = state.get("characters", [])
            moral_message = state.get("moral_message", "")
            theme = state.get("theme", "")

            if not story_content:
                logger.warning("[SUTRADARA::PERINGATAN] Cerita belum tersedia di state, saya tidak bisa membuat skrip tanpa konten cerita.")
                return {}

            # Build characters summary for the prompt
            char_summary = ""
            if characters:
                char_lines = []
                for c in characters:
                    if isinstance(c, dict):
                        name = c.get("name", "")
                        role = c.get("role", "")
                        char_lines.append(f"- {name}: {role}" if role else f"- {name}")
                char_summary = "\n".join(char_lines)

            # Load bilingual system prompt
            registry = get_registry()
            system_prompt = registry.get("director")

            # Build user message
            user_message = (
                f"Judul/Tema: {theme}\n\n"
                f"Pesan Moral: {moral_message}\n\n"
                f"Karakter:\n{char_summary}\n\n"
                f"===== CERITA =====\n{story_content}"
            )

            logger.info(f"[SUTRADARA::MEMPROSES] Saya sedang mengubah cerita menjadi skrip dialog beranotasi via LLM, tema: {theme}, pesan moral: {moral_message}.")
            messages = [
                ("system", system_prompt),
                ("human", user_message),
            ]
            script_output: ScriptOutput = await self.structured_llm.ainvoke(messages)

            # Render to annotated .md
            md_text = self._render_script_to_md(script_output)

            # Write to output directory
            output_dir = _script_output_dir()
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(
                    f"[SUTRADARA::SKIP_DIR] Tidak bisa membuat direktori skrip ({output_dir}): {e}"
                )
            output_path = output_dir / f"{session_id}_script.md"
            script_file_path = ""
            try:
                output_path.write_text(md_text, encoding="utf-8")
                script_file_path = str(output_path)
            except OSError as e:
                logger.warning(
                    f"[SUTRADARA::SKIP_SAVE] Tidak bisa menulis skrip ke disk ({output_path}): {e}"
                )

            elapsed = time.time() - start_time
            if script_file_path:
                logger.success(
                    f"[SUTRADARA::SELESAI] Skrip dialog selesai: {script_output.scene_count} adegan berhasil disusun "
                    f"dan disimpan ke {script_file_path} dalam {elapsed:.1f} detik."
                )
            else:
                logger.success(
                    f"[SUTRADARA::SELESAI] Skrip dialog selesai: {script_output.scene_count} adegan berhasil disusun "
                    f"(tanpa penyimpanan file) dalam {elapsed:.1f} detik."
                )

            if self.langfuse and span_id:
                self.langfuse.end_span(
                    span_id=span_id,
                    output_data={
                        "scene_count": script_output.scene_count,
                        "file_path": script_file_path,
                        "elapsed_time": round(elapsed, 2)
                    }
                )

            return {
                "draft_script": md_text,
                "script_file_path": script_file_path,
                "script_scene_count": script_output.scene_count,
            }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"[SUTRADARA::GAGAL] Saya tidak berhasil membuat skrip dialog, alasan: {e}\n{error_trace}")

            if self.langfuse and span_id:
                self.langfuse.end_span(
                    span_id=span_id,
                    output_data={"error": str(e)}
                )

            return {
                "draft_script": "",
                "script_file_path": "",
                "script_scene_count": 0,
            }

    def _render_script_to_md(self, script: ScriptOutput) -> str:
        """
        Render ScriptOutput ke format .md beranotasi.

        Setiap blok scene ditulis sebagai:
            <!-- {"type": "...", "character": "...", "time": "...", "scene": "..."} -->
            **Karakter:** Teks dialog.

        Returns:
            String konten .md lengkap dengan anotasi JSON per scene.
        """
        lines = [f"# {script.title}\n"]

        for scene in script.scenes:
            # Build JSON annotation dict
            annotation: Dict = {"type": scene.scene_type}
            if scene.character:
                annotation["character"] = scene.character
            if scene.time_hint:
                annotation["time"] = scene.time_hint
            if scene.scene_setting:
                annotation["scene"] = scene.scene_setting

            lines.append(f"<!-- {json.dumps(annotation, ensure_ascii=False)} -->")

            # Format text body by scene type
            if scene.scene_type == "dialog" and scene.character:
                lines.append(f"**{scene.character}:** {scene.text}")
            elif scene.scene_type == "transisi":
                lines.append(f"*{scene.text}*")
            else:
                lines.append(scene.text)

            # Append optional narrator context note
            if scene.narrator_text:
                narrator_annotation = {"type": "narrator_note"}
                lines.append(f"<!-- {json.dumps(narrator_annotation, ensure_ascii=False)} -->")
                lines.append(f"> {scene.narrator_text}")

            lines.append("")  # blank line between scenes

        return "\n".join(lines)
