"""
Writer Agent - Drafts the educational story
With structured output using Pydantic
With canvas-based revision system for targeted editing
With Langfuse observability integration
"""

import json
import re
import time
from typing import Optional, List
from pydantic import BaseModel, Field
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import StoryState
from ..prompts import get_registry
from ..story_canvas import StoryCanvas, StructuredCritique
from settings import ModelConfig, StoryConfig, LanguageConfig
from providers.llm_factory import get_llm_for_agent

# Import Langfuse for observability
try:
    from ..integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None

class StoryDraft(BaseModel):
    """Structured output for story drafting"""
    title: str = Field(..., description="The title of the story")
    content: str = Field(..., description="The full story content in markdown format. MUST be a complete story with a proper ending.")
    references: List[str] = Field(default_factory=list, description="List of source URIs/links found in research_notes that were actually used in the story.")

class StoryEdit(BaseModel):
    """A single edit operation"""
    search: str = Field(..., description="The EXACT text segment to replace (must match unique phrase in story)")
    replace: str = Field(..., description="The new text to insert in place of the search text")

class StoryRevision(BaseModel):
    """Set of edits to improve the story"""
    edits: List[StoryEdit] = Field(..., description="List of edits to apply")
    thought_process: str = Field(..., description="Explanation of why these edits are being made" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Penjelasan mengapa perubahan ini dilakukan")

class WriterDraftingInput(BaseModel):
    metric: str = "writer_drafting"
    model: str
    system_prompt: str
    user_input: str
    language: str
    target_age: str
    theme: str
    story_length: str
    narrative_style: str

class WriterRevisionInput(BaseModel):
    metric: str = "writer_revision_planning"
    model: str
    system_prompt: str
    revision_num: int
    critique_feedback: str
    current_story_length: int

class WriterFallbackInput(BaseModel):
    metric: str = "writer_revision_fallback"
    model: str
    is_fallback: bool = True
    system_prompt: str


class WriterAgent:
    """
    Drafts engaging educational stories with canvas-based revision.
    
    - First draft: Full story generation using structured Pydantic output
    - Revisions: Targeted paragraph-level edits via RevisionAgent
    """
    
    def __init__(self, model_name: str = None, credentials=None, project=None):
        self.model_name = model_name or ModelConfig.GEMINI_MODEL
        # credentials / project kept for backward-compat, ignored for non-Google providers
        self.llm = get_llm_for_agent("writer", model_name=self.model_name)
        self.credentials = credentials
        self.project = project
        
        # Initialize structured LLM
        # Initialize structured LLM for drafting
        self.draft_llm = self.llm.with_structured_output(StoryDraft)
        
        # Initialize structured LLM for revision
        self.revision_llm = self.llm.with_structured_output(StoryRevision)
        
        # Initialize Langfuse for observability
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None

    
    async def write(self, state: StoryState) -> dict:
        """
        Write or revise the story draft.
        
        - First call (revision_count=0): Generate full draft
        - Subsequent calls: Use RevisionAgent for targeted paragraph edits
        
        Returns: Updated state with draft_content and canvas
        """
        
        revision_num = state.get("revision_count", 0)
        
        # Check if text writer is active
        active_writers = state.get("active_writers", ["text"])
        if "text" not in active_writers:
            logger.info("[PENULIS::LEWATI] Penulis sedang istirahat (tidak aktif).")
            return {}
        
        # Check revision flag on subsequent passes
        if revision_num > 0 and not state.get("needs_text_revision", True):
            logger.info("[PENULIS::LEWATI] Teks cerita tidak perlu direvisi kali ini, saya lewati dulu.")
            return {}

        
        # Start Langfuse span for writing
        writer_span_id = None
        start_time = time.time()
        if self.langfuse:
            writer_span_id = self.langfuse.start_span(
                name="writer_agent",
                input_data={
                    "revision_num": revision_num,
                    "is_revision": revision_num > 0,
                    "language": state.get("language", "Indonesian"),
                    "story_length": state.get("story_length", "medium"),
                    "narrative_style": state.get("narrative_style", "campuran"),
                    "target_age": state.get("target_age", ""),
                    "theme": state.get("theme", ""),
                },
                metadata={"agent": "writer", "is_revision": revision_num > 0}
            )
        
        try:
            if revision_num == 0:
                # First draft - full generation
                result = await self._write_first_draft(state)
            else:
                # Revision - targeted edits via canvas
                result = await self._targeted_revision(state)
            
            # End span with success metrics
            if self.langfuse and writer_span_id:
                elapsed_time = time.time() - start_time
                draft_content = result.get("draft_content", "")
                self.langfuse.end_span(
                    span_id=writer_span_id,
                    output_data={
                        "is_revision": revision_num > 0,
                        "chars": {"output_chars": len(draft_content)},
                        "word_count": len(draft_content.split()),
                        "elapsed_time_seconds": round(elapsed_time, 2)
                    }
                )
            
            # Save draft to file (optional; serverless filesystem is read-only outside /tmp)
            import os
            import tempfile
            draft_content = result.get("draft_content", "")
            raw_title = state.get("theme", "story") or "story"
            title_slug = re.sub(r'[^\w\s-]', '', raw_title).strip().replace(" ", "_")[:40]
            title_slug = title_slug or "story"
            is_serverless = bool(
                os.getenv("VERCEL")
                or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
                or os.getenv("LAMBDA_TASK_ROOT")
            )
            base = os.path.join(tempfile.gettempdir(), "skripsi") if is_serverless else "."
            filename = os.path.join(base, "output", "drafts", f"{title_slug}_v{revision_num}.md")
            try:
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(draft_content)
                logger.info(f"[PENULIS::MENYIMPAN] Draf selesai, saya simpan ke {filename}")
            except OSError as e:
                logger.warning(f"[PENULIS::SKIP_SAVE] Tidak bisa menyimpan draf ke disk ({filename}): {e}")
            
            return result
            
        except Exception as e:
            # End span with error
            if self.langfuse and writer_span_id:
                self.langfuse.end_span(
                    span_id=writer_span_id,
                    output_data={"error": str(e)}
                )
            raise
    
    async def _write_first_draft(self, state: StoryState) -> dict:
        """Generate the initial story draft and initialize canvas"""
        # Get settings
        language = state.get("language", StoryConfig.get_default_language())
        story_length = state.get("story_length", StoryConfig.DEFAULT_STORY_LENGTH)
        narrative_style = state.get("narrative_style", "campuran")
        
        # Narrative style instructions
        from settings import LanguageConfig
        sys_lang = LanguageConfig.SYSTEM_LANGUAGE
        
        narrative_instructions = {
            "id": {
                "campuran": "Seimbangkan antara narasi dan dialog secara alami",
                "dialog_dominan": "Gunakan LEBIH BANYAK DIALOG antar karakter, narasi minimal.",
                "monolog_dominan": "Gunakan LEBIH BANYAK NARASI dan deskripsi, dialog minimal.",
                "monolog_internal": "Fokus pada PIKIRAN DAN PERASAAN INTERNAL KARAKTER.",
                "dialog_murni": "Tulis HAMPIR SELURUHNYA dalam dialog, seperti naskah drama.",
                "non_dialog": "Tulis HANYA narasi dan deskripsi. TANPA DIALOG SAMA SEKALI.",
                "deskriptif": "Tulis narasi murni yang deskriptif."
            },
            "en": {
                "campuran": "Balance between narration and dialogue naturally",
                "dialog_dominan": "Use MORE DIALOGUE between characters, minimal narration.",
                "monolog_dominan": "Use MORE NARRATION and description, minimal dialogue.",
                "monolog_internal": "Focus on CHARACTER'S INTERNAL THOUGHTS and feelings.",
                "dialog_murni": "Write ALMOST ENTIRELY in dialogue, like a play script.",
                "non_dialog": "Write ONLY narration and description. NO DIALOGUE AT ALL.",
                "deskriptif": "Write purely descriptive prose."
            }
        }
        
        lang_dict = narrative_instructions.get(sys_lang, narrative_instructions["id"])
        narrative_guide = lang_dict.get(narrative_style, lang_dict["campuran"])
        
        # Build enhanced prompt
        registry = get_registry()
        writing_constraints = registry.get("writer_instructions").format(
            language_upper=language.upper(),
            story_length=story_length,
            narrative_style=narrative_style,
            narrative_guide=narrative_guide,
        )

        base_prompt = registry.get("writer").format(
            target_age=state.get("target_age", StoryConfig.DEFAULT_TARGET_AGE),
            emotional_tone=state.get("emotional_tone", StoryConfig.DEFAULT_EMOTIONAL_TONE),
            theme=state.get("theme", ""),
            story_style=state.get("story_style", StoryConfig.DEFAULT_STORY_STYLE),
            story_length=story_length,
            story_outline=str(state.get("story_outline", {})),
            characters=str(state.get("characters", [])),
            moral_message=state.get("moral_message", ""),
            research_notes=state.get("research_notes", "")[:65536],
            critique_feedback="None - first draft",
            writing_constraints=writing_constraints,
        )

        enhanced_prompt = base_prompt

        # Injeksikan catatan refleksi dari sesi sebelumnya jika tersedia
        past_reflections = state.get("past_reflections", "")
        if past_reflections:
            enhanced_prompt += f"\n\n{past_reflections}"
            logger.info("[PENULIS::REFLEKSI] Catatan refleksi dari sesi sebelumnya diinjeksikan ke prompt.")

        messages = [
            SystemMessage(content=enhanced_prompt),
            HumanMessage(content=registry.get("writer_user").format(
                language=language,
                story_length=story_length,
                narrative_style=narrative_style,
                user_prompt=state.get("user_message", "")
            ))
        ]
        
        logger.info(f"[PENULIS::MENULIS] Mulai menulis draf pertama dalam bahasa {language}...")
        logger.info(f"[PENULIS::MENULIS] Gaya narasi: {narrative_style} | Target panjang: {story_length}")
        
        # Generate with Structured Output
        # Note: We rely on the underlying retry mechanism of LangChain if configured, 
        # or we could wrap this in a retry block.
        response = await self.draft_llm.ainvoke(messages)
        story_draft = response.content
        story_title = response.title
        
        # Log generation
        if self.langfuse:
            input_payload = WriterDraftingInput(
                model=self.model_name,
                system_prompt=enhanced_prompt,
                user_input=state.get("user_message", ""),
                language=language,
                target_age=state.get("target_age", ""),
                theme=state.get("theme", ""),
                story_length=story_length,
                narrative_style=narrative_style,
            )
            self.langfuse.log_generation(
                name="writer_drafting",
                model=self.model_name,
                input_text=input_payload.model_dump_json(indent=2),
                output_text=response.model_dump_json(indent=2),
                metadata={"title": story_title, "length": len(story_draft)}
            )

        # Fallback: Extract title from content if missing
        if not story_title or not story_title.strip():
            logger.warning("[PENULIS::JUDUL] Judul tidak ditemukan dari model, saya coba ambil dari baris pertama isi cerita...")
            for line in story_draft.split('\n')[:5]:
                clean_line = line.strip()
                if clean_line.startswith('# '):
                    story_title = clean_line.replace('#', '').strip()
                    break
        
        word_count = len(story_draft.split())
        logger.success(f"[PENULIS::SELESAI] Draf pertama selesai ditulis! Judul: \"{story_title}\" | {word_count} kata | {len(story_draft)} karakter.")
        
        # Initialize canvas with the draft
        canvas = StoryCanvas()
        para_count = canvas.initialize_from_text(story_draft, title=story_title)
        
        return {
            "draft_content": story_draft,
            "draft_title": story_title,
            "current_stage": "critique",
            "story_canvas": canvas.to_dict(),
            "used_sources": response.references,  # Pass selected references to state
            "revision_history": [{
                "version": 0,
                "content": story_draft,
                "feedback_received": "(initial draft)",
                "paragraph_count": para_count
            }],
            "messages": [{"role": "writer", "content": story_draft}]
        }
    
    async def _targeted_revision(self, state: StoryState) -> dict:
        """
        Perform targeted revision using Search/Replace pattern (MCP-style) via vendor tool.
        """
        import tempfile
        import os
        from ..integrations.vendor_file_edit import replace_in_files
        
        revision_num = state.get("revision_count", 0)
        current_story = state.get("draft_content", "")
        critique_feedback = state.get("critique_feedback", "")
        
        logger.info(f"[PENULIS::MEREVISI] Saatnya merevisi, ini revisi ke-{revision_num}. Saya akan cermati masukan kritik dan perbaiki bagian yang perlu diperbaiki.")
        if critique_feedback:
            logger.info(f"[PENULIS::MASUKAN] Masukan yang akan saya tindaklanjuti: {critique_feedback}")
        
        if not current_story:
            logger.warning("[PENULIS::MEREVISI] Belum ada cerita yang bisa direvisi!")
            return {}

        # Get original constraints
        language = state.get("language", "Indonesian")
        story_length = state.get("story_length", "medium")
        narrative_style = state.get("narrative_style", "campuran")
        
        registry = get_registry()
        user_constraints = registry.get("writer_user").format(
            language=language,
            story_length=story_length,
            narrative_style=narrative_style,
            user_prompt=state.get("user_message", "")
        )

        # Construct prompt for revision
        prompt = registry.get("writer_revision").format(
            user_constraints=user_constraints,
            critic_feedback=critique_feedback,
            current_draft=current_story,
            target_age=state.get("target_age", "8-10"),
            story_style=state.get("story_style", "naratif"),
            theme=state.get("theme", ""),
            research_notes=state.get("research_notes", "")[:32768]  # Cap at 32k to avoid token overflow
        )
        
        is_en = language.lower() in ["en", "english"]
        system_msg = "You are a precise editor using search/replace tools. Provide your thought process in English." if is_en else "Anda adalah editor presisi menggunakan alat cari/ganti. Berikan proses berpikir Anda dalam Bahasa Indonesia."
        
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=prompt)
        ]
        
        try:
            # Generate edits
            response: StoryRevision = await self.revision_llm.ainvoke(messages)
            
            # Log generation
            if self.langfuse:
                input_payload = WriterRevisionInput(
                    model=self.model_name,
                    system_prompt=prompt,
                    revision_num=revision_num,
                    critique_feedback=critique_feedback,
                    current_story_length=len(current_story),
                )
                self.langfuse.log_generation(
                    name="writer_revision_planning",
                    model=self.model_name,
                    input_text=input_payload.model_dump_json(indent=2),
                    output_text=response.model_dump_json(indent=2),
                    metadata={
                        "edit_count": len(response.edits),
                        "thought_process": response.thought_process
                    }
                )
            
            logger.info(f"[PENULIS::MEREVISI] Saya usulkan {len(response.edits)} perbaikan. Alasan: {response.thought_process}")
            
            # Create temp file for the story
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                tmp.write(current_story)
                tmp_path = tmp.name
                
            successful_edits = 0
            
            try:
                # Apply edits using the vendor tool directly
                for edit in response.edits:
                    # replace_in_files expects a directory or file path
                    # we pass the specific file path
                    # IMPORTANT: We must escape the search text because replace_in_files
                    # compiles it as a regex, but the LLM provides literal text.
                    import re
                    search_pattern = re.escape(edit.search)
                    
                    result = await replace_in_files(
                        search=search_pattern,
                        replace=edit.replace,
                        path=tmp_path,
                        recursive=False
                    )
                    
                    if result.get("completed") and result.get("files_processed", 0) > 0:
                        # Check if any replacements actually happened
                        # The result structure from our vendor tool: {'results': [{'file':..., 'replacements': N}], ...}
                        file_results = result.get("results", [])
                        if file_results and file_results[0].get("replacements", 0) > 0:
                            successful_edits += 1
                        else:
                            logger.warning(f"[PENULIS::MEREVISI] Teks ini tidak ditemukan dalam cerita, saya lewati: '{edit.search[:50]}'")
                else:
                    logger.warning(f"[PENULIS::MEREVISI] Alat pengeditan gagal dijalankan untuk: '{edit.search[:50]}', {result.get('error')}")
                # Read back the modified file
                with open(tmp_path, 'r', encoding='utf-8') as f:
                    new_story = f.read()
                    
            finally:
                # Cleanup
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            logger.success(f"[PENULIS::SELESAI] Revisi ke-{revision_num} selesai! Berhasil menerapkan {successful_edits} dari {len(response.edits)} perbaikan.")
            
            # Update revision history
            revision_history = list(state.get("revision_history", []))
            revision_history.append({
                "version": revision_num,
                "content": new_story,
                "feedback_received": critique_feedback,
                "edits_proposed": len(response.edits),
                "edits_applied": successful_edits,
                "thought_process": response.thought_process
            })
            
            return {
                "draft_content": new_story,
                "current_stage": "critique",
                "revision_history": revision_history,
                "messages": [{"role": "writer", "content": f"[Revisi {revision_num}] {new_story}"}]
            }
            
        except Exception as e:
            logger.error(f"[PENULIS::GALAT] Terjadi masalah saat melakukan revisi: {e}")
            return {}

    
    async def _fallback_full_revision(self, state: StoryState, canvas: StoryCanvas) -> dict:
        """
        Fallback to full revision when no specific paragraphs are flagged.
        Uses structured output now.
        """
        language = state.get("language", StoryConfig.DEFAULT_LANGUAGE)
        story_length = state.get("story_length", StoryConfig.DEFAULT_STORY_LENGTH)
        revision_num = state.get("revision_count", 0)
        narrative_style = state.get("narrative_style", "campuran")
        critique_feedback = state.get("critique_feedback", "")

        registry = get_registry()
        user_constraints = registry.get("writer_user").format(
            user_prompt=state.get("user_message", "")
        )
        
        enhanced_prompt = registry.get("writer_revision_fallback").format(
            critique_feedback=critique_feedback,
            user_constraints=user_constraints
        )

        messages = [
            SystemMessage(content=registry.get("writer")), # Reusing base prompt context
            HumanMessage(content=enhanced_prompt)
        ]
        
        logger.warning("[PENULIS::CADANGAN] Tidak ada paragraf spesifik yang bisa ditarget, saya tulis ulang cerita secara penuh sebagai cadangan.")
        
        # Use draft_llm which is configured for StoryDraft
        response = await self.draft_llm.ainvoke(messages)
        story_draft = response.content
        story_title = response.title
        
        # Log generation
        if self.langfuse:
            input_payload = WriterFallbackInput(model=self.model_name, system_prompt=enhanced_prompt)
            self.langfuse.log_generation(
                name="writer_revision_fallback",
                model=self.model_name,
                input_text=input_payload.model_dump_json(indent=2),
                output_text=response.model_dump_json(indent=2),
                metadata={"title": story_title, "length": len(story_draft), "is_fallback": True}
            )
        
        # Reinitialize canvas with new draft
        canvas = StoryCanvas()
        canvas.initialize_from_text(story_draft, title=story_title)
        
        revision_history = list(state.get("revision_history", []))
        revision_history.append({
            "version": revision_num,
            "content": story_draft,
            "feedback_received": critique_feedback,
            "paragraph_count": len(canvas.paragraphs),
            "edits_applied": "full_rewrite"
        })
        
        return {
            "draft_content": story_draft,
            "current_stage": "critique",
            "story_canvas": canvas.to_dict(),
            "revision_history": revision_history,
            "messages": [{"role": "writer", "content": story_draft}]
        }
    
    def _show_canvas_changes(self, canvas: StoryCanvas, revision_num: int):
        """Show canvas-based change summary"""
        history = canvas.get_revision_history_summary()
        
        if len(history) < 2:
            return
        
        current = history[-1]
        previous = history[-2]
        
        logger.info(f"[PENULIS::KANVAS] RIWAYAT KANVAS: Versi {previous['version']} -> {current['version']}")
