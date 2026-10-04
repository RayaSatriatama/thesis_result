"""
Planner Agent - Creates story outline and characters
With Langfuse observability integration
With 429 Rate Limit retry support
With Pydantic Structured Output for reliable parsing
"""

import json
import re
import time
from typing import List, Optional
from pydantic import BaseModel, Field
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import StoryState
from ..prompts import get_registry
from ..utils.retry import invoke_with_retry
from settings import ModelConfig, StoryConfig, LanguageConfig
from providers.llm_factory import get_llm_for_agent


# === PYDANTIC MODELS FOR STRUCTURED OUTPUT ===

class StoryOutline(BaseModel):
    """Story framework with narrative structure"""
    introduction: str = Field(description="Story setup: introduction of characters, setting, and initial situation")
    conflict: str = Field(description="Main problem or challenge faced by the characters")
    climax: str = Field(description="Story peak: the most intense/exciting moment")
    resolution: str = Field(description="Story resolution and learning outcome")

class StoryCharacter(BaseModel):
    """Characters in the story"""
    name: str = Field(description="Character name")
    age: str = Field(description="Character age (e.g., '10 years' or 'adult')")
    personality: str = Field(description="Character personality and traits")
    role: str = Field(description="Role in story (protagonist, antagonist, supporting)")


class PlannerOutput(BaseModel):
    """
    Unified Planner output - combines parsing, planning, and writer selection.
    All determined in ONE LLM call.
    """
    # === PARSED REQUEST PARAMS (from user message analysis) ===
    theme: str = Field(description="Main story theme identified from user request")
    target_age: str = Field(
        description="Target age group: 5-7, 8-10, 11-13, 14-17, or 18+",
        default=""
    )
    learning_objectives: str = Field(
        description="Learning objectives to be achieved",
        default=""
    )
    story_style: str = Field(
        description="Specific story style (e.g., 'Educational Fable', 'Science Mystery', 'History Adventure'). DO NOT use 'general'.",
        default=""
    )
    narrative_style: str = Field(
        description="Narrative style: mixed, dialogue_dominant, monologue_dominant, or descriptive",
        default=""
    )
    emotional_tone: str = Field(
        description="Specific emotional tone (e.g., 'Curious', 'Tense but educational'). DO NOT default to 'warm' if not appropriate.",
        default="warm"
    )
    setting_ideas: str = Field(description="Detailed ideas for setting/location", default="")
    character_ideas: str = Field(description="Unique character ideas", default="")
    story_length: str = Field(
        description="CLEAR & DESCRIPTIVE story length estimate (e.g., '300-500 words', 'Short story 5 paragraphs'). DO NOT use 'medium' or 'long' without detail. REQUIRED."
    )

    # === STORY PLAN (constructed by planner) ===
    draft_title: str = Field(description="Creative and engaging story title")
    story_outline: StoryOutline = Field(description="Complete story outline")
    characters: List[StoryCharacter] = Field(description="List of characters in the story")
    moral_message: str = Field(description="Moral message or takeaway of the story")

    # === PLANNER DECISION (which writers to activate) ===
    active_writers: List[str] = Field(
        description="Active writers: 'text' (required), 'image' (for visual stories), 'diagram' (for science/technical stories)",
        default=["text"]
    )
    writer_reasoning: str = Field(
        description="Brief reasoning for writer selection" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Alasan singkat pemilihan penulis",
        default=""
    )


# Keep old model for backwards compatibility
class PlannerDecision(BaseModel):
    """DEPRECATED - Use PlannerOutput instead"""
    active_writers: List[str] = Field(default=["text"])
    reasoning: str = Field(default="")


class PlannerInput(BaseModel):
    """Structured input payload logged to Langfuse for planner_unified_call."""
    metric: str = "planner_unified_call"
    model: str
    system_prompt: str
    user_input: str
    language: str
    story_length: str
    research_notes: str


# Import Langfuse for observability
try:
    from ..integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None


class PlannerAgent:
    """Creates story structure and characters using structured output"""

    def __init__(self, model_name: Optional[str] = None, credentials=None, project=None):
        self.model_name = model_name or ModelConfig.GEMINI_MODEL
        # credentials / project kept for backward-compat, ignored for non-Google providers
        self.llm = get_llm_for_agent("planner", model_name=self.model_name)
        # Backward compatibility for legacy helper path (_parse_user_request).
        self.parser_llm = self.llm
        self.credentials = credentials
        self.project = project

        # Initialize Langfuse for observability
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None

        # Use structured output mode by default
        self.use_structured_output = True

    def _sanitize_json(self, json_str: str) -> str:
        """
        Sanitize common JSON issues from LLM output.
        Fixes issues like unquoted values: "age": 60-an → "age": "60-an"
        """
        import re

        # Fix unquoted values that look like: "key": value-something or "key": value123abc
        # Pattern matches: "key": followed by unquoted value containing letters/numbers/hyphens
        def fix_unquoted_value(match):
            key = match.group(1)
            value = match.group(2)
            return f'"{key}": "{value}"'

        # Fix patterns like "age": 60-an or "something": abc123
        json_str = re.sub(
            r'"([^"]+)":\s*([a-zA-Z0-9][a-zA-Z0-9\-]+[a-zA-Z])(?=[,}\s\n])',
            fix_unquoted_value,
            json_str
        )

        # Also fix simple unquoted strings after colon
        json_str = re.sub(
            r'"([^"]+)":\s*([a-zA-Z][a-zA-Z0-9\s\-]+)(?=[,}\n])',
            fix_unquoted_value,
            json_str
        )

        return json_str

    def _is_short_story(self, story_length: str) -> bool:
        """
        Detect if the story should be short/concise based on story_length parameter.
        """
        short_indicators = [
            "sangat_pendek", "sangat pendek", "very_short", "very short",
            "pendek", "short", "singkat", "brief",
            "1-3 paragraf", "1-3 paragraph",
            "50-200 kata", "200 kata", "100 kata", "150 kata",
            "3 kalimat", "5 kalimat", "10 kalimat",
            "1 paragraf", "2 paragraf", "3 paragraf"
        ]
        story_length_lower = story_length.lower()
        return any(indicator in story_length_lower for indicator in short_indicators)

    def _resolve_prompt_language(self, language: str) -> str:
        """
        Resolve prompt registry language code from state language value.
        """
        lang = (language or "").strip().lower()
        if lang in {"en", "english"}:
            return "en"
        return "id"

    def _get_concise_instructions(self, story_length: str, language: str) -> str:
        """
        Generate concise planning instructions for short stories.
        """
        registry = get_registry(self._resolve_prompt_language(language))
        return registry.get("planner_short_guide").format(story_length=story_length)

    async def _parse_user_request(self, user_message: str) -> dict:
        """
        Parse natural language request into structured story parameters.
        This runs INSIDE the planner_agent span for unified Langfuse tracing.

        Returns dict with story parameters.
        """
        registry = get_registry(self._resolve_prompt_language(StoryConfig.get_default_language()))
        prompt = registry.get("planner_parser").format(user_message=user_message)
        try:
            messages = [HumanMessage(content=prompt)]
            response = await self.parser_llm.ainvoke(messages)
            text = response.content

            def extract_field(pattern, default=""):
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    next_field = re.search(r'\n(?:LEARNING_OBJECTIVES|TARGET_AGE|THEME|STORY_STYLE|NARRATIVE_STYLE|EMOTIONAL_TONE|SETTINGS|CHARACTERS|ADDITIONAL|LANGUAGE|STORY_LENGTH):', content)
                    if next_field:
                        content = content[:next_field.start()].strip()
                    if content in ['""', "''", ""]:
                        return ""
                    return content
                return default

            return {
                "learning_objectives": extract_field(r'LEARNING_OBJECTIVES:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "target_age": extract_field(r'TARGET_AGE:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "theme": extract_field(r'THEME:\s*(.+?)(?=\n[A-Z_]+:|$)', user_message),
                "story_style": extract_field(r'STORY_STYLE:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "narrative_style": extract_field(r'NARRATIVE_STYLE:\s*(.+?)(?=\n[A-Z_]+:|$)', "campuran"),
                "emotional_tone": extract_field(r'EMOTIONAL_TONE:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "setting_suggestions": extract_field(r'SETTINGS:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "character_suggestions": extract_field(r'CHARACTERS:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "additional_context": extract_field(r'ADDITIONAL:\s*(.+?)(?=\n[A-Z_]+:|$)', ""),
                "language": extract_field(r'LANGUAGE:\s*(.+?)(?=\n[A-Z_]+:|$)', StoryConfig.DEFAULT_LANGUAGE) or StoryConfig.DEFAULT_LANGUAGE,
                "story_length": extract_field(r'STORY_LENGTH:\s*(.+?)(?=\n[A-Z_]+:|$)', StoryConfig.DEFAULT_STORY_LENGTH) or StoryConfig.DEFAULT_STORY_LENGTH
            }
        except Exception as e:
            logger.warning(f"Parsing failed: {e}, using defaults")
            return {
                "theme": user_message,
                "target_age": StoryConfig.DEFAULT_TARGET_AGE,
                "story_style": StoryConfig.DEFAULT_STORY_STYLE,
                "language": StoryConfig.DEFAULT_LANGUAGE,
                "story_length": StoryConfig.DEFAULT_STORY_LENGTH,
                "narrative_style": "campuran"
            }

    async def plan(self, state: StoryState) -> dict:
        """
        Unified Planner - ONE LLM call that:
        1. Analyzes user request → determines target_age, story_style, etc.
        2. Creates story plan → outline, characters, moral_message
        3. Decides which writers to activate → text, image, diagram

        Returns: Updated state with ALL parsed params + story plan
        """
        # Start Langfuse span for planner agent
        plan_span_id = None
        start_time = time.time()
        user_message = state.get("user_message", "") or state.get("theme", "")
        story_length = state.get("story_length", "")
        language = state.get("language", "Indonesian")
        research_notes = state.get("research_notes", "")
        requested_target_age = str(state.get("target_age", "") or "").strip()

        # Alur interaktif: supervisor_node selalu dijalankan lebih dulu; untuk cerita baru
        # keputusan umumnya «planning» — log ini memperjelas urutan di terminal.
        if state.get("supervisor_next") or state.get("interaction_mode"):
            logger.info(
                "[PERENCANA::MULAI] Alur interaktif: supervisor sudah memutuskan langkah berikutnya; "
                "saya lanjut menyusun rencana cerita."
            )
        else:
            logger.info("[PERENCANA::MULAI] Oke, saya baca dulu permintaan ini baik-baik...")
        logger.info(f"[PERENCANA::MULAI] Permintaan yang masuk: \"{user_message}\"")
        if story_length:
            logger.info(f"[PERENCANA::MULAI] Target panjang cerita: {story_length}")
        if research_notes:
            logger.info(f"[PERENCANA::MULAI] Ada {len(research_notes)} karakter catatan riset yang bisa saya jadikan referensi, bagus!")

        # Determine if short story
        is_short = self._is_short_story(story_length)
        concise_section = self._get_concise_instructions(story_length, language) if is_short else ""

        # Robust language check
        is_en = language.lower() in ["en", "english"]

        # Build UNIFIED planner prompt (parsing + planning in ONE call)
        # Built BEFORE start_span so it can be included in input_data
        prompt_lang = self._resolve_prompt_language(language)
        registry = get_registry(prompt_lang)
        unified_prompt = registry.get("planner_unified").format(
            user_message=user_message,
            research_notes=research_notes if research_notes else ("(No preliminary research)" if is_en else "(Tidak ada riset pendahuluan)"),
            concise_section=concise_section,
            language=language,
            story_length=story_length
        )

        # Start Langfuse span AFTER prompt is built - include full prompt in INPUT
        if self.langfuse:
            plan_span_id = self.langfuse.start_span(
                name="planner_agent",
                input_data={
                    "user_input": user_message,
                    "language": language,
                    "story_length": story_length,
                },
                metadata={"agent": "planner", "unified": True, "model": self.model_name}
            )

        # Build messages for unified LLM call
        msg_content = f"Analyze request and create story plan for: {user_message}" if is_en else f"Analisis permintaan dan buat rencana cerita untuk: {user_message}"
        messages = [
            SystemMessage(content=unified_prompt),
            HumanMessage(content=msg_content)
        ]

        # Use STRUCTURED OUTPUT for unified planner call
        try:
            logger.debug("[PERENCANA::BERPIKIR] Sedang menganalisis permintaan dan merancang seluruh struktur cerita dalam satu langkah...")
            structured_llm = self.llm.with_structured_output(PlannerOutput)

            # Use retry for rate limit handling
            result: PlannerOutput = await invoke_with_retry(
                structured_llm,
                messages,
                max_retries=3,
                base_delay=3.0,
                max_delay=30.0
            )

            # Extract ALL data from unified result
            theme = result.theme
            # An explicit API/request value is an experiment constraint. The
            # planner may infer an age only when the caller left it blank.
            target_age = requested_target_age or result.target_age
            learning_objectives = result.learning_objectives or ""
            story_style = result.story_style
            narrative_style = result.narrative_style
            emotional_tone = result.emotional_tone or ("warm" if is_en else "hangat")
            setting_ideas = result.setting_ideas or ""
            character_ideas = result.character_ideas or ""
            story_length_result = result.story_length or story_length

            # Log generation for unified planner
            if self.langfuse:
                self.langfuse.log_generation(
                    name="planner_unified_call",
                    model=self.model_name,
                    input_text=PlannerInput(
                        model=self.model_name,
                        system_prompt=unified_prompt,
                        user_input=user_message,
                        language=language,
                        story_length=story_length,
                        research_notes=research_notes,
                    ).model_dump_json(indent=2),
                    output_text=result.model_dump_json(indent=2),
                    metadata={
                        "theme": theme,
                        "target_age": target_age,
                        "writers": str(result.active_writers)
                    }
                )

            outline = {
                "introduction": result.story_outline.introduction,
                "conflict": result.story_outline.conflict,
                "climax": result.story_outline.climax,
                "resolution": result.story_outline.resolution
            }

            characters = [
                {
                    "name": char.name,
                    "age": char.age,
                    "personality": char.personality,
                    "role": char.role
                }
                for char in result.characters
            ]

            moral = result.moral_message
            # Check if active_writers was provided in input state (override LLM decision)
            input_active_writers = state.get("active_writers")
            if input_active_writers and len(input_active_writers) > 0:
                logger.info(f"[PERENCANA::MEMUTUSKAN] Tim penulis sudah ditentukan sebelumnya oleh pengguna, saya ikuti saja: {input_active_writers}")
                active_writers = input_active_writers
            else:
                active_writers = result.active_writers if result.active_writers else ["text"]

            # Filter writers based on feature flags (unless explicitly overridden by user)
            if not input_active_writers:
                filtered_writers = ["text"] # Text is always allowed
                if "image" in active_writers and StoryConfig.ENABLE_IMAGE_WRITER:
                    filtered_writers.append("image")
                if "diagram" in active_writers and StoryConfig.ENABLE_DIAGRAM_WRITER:
                    filtered_writers.append("diagram")

                if len(filtered_writers) < len(active_writers):
                    disabled = [w for w in active_writers if w not in filtered_writers]
                    logger.info(f"[PERENCANA::MEMUTUSKAN] {disabled} tidak aktif saat ini berdasarkan konfigurasi sistem. Tim yang akan bekerja: {filtered_writers}")
                active_writers = filtered_writers

            # Ensure "text" is always present
            if "text" not in active_writers:
                active_writers.insert(0, "text")

            draft_title = result.draft_title
            plan_text = f"Theme: {theme}\nOutline: {outline}\nCharacters: {characters}\nMoral: {moral}"

            # Display result
            elapsed_so_far = round(time.time() - start_time, 2)
            logger.success(f"[PERENCANA::SELESAI] Rencana cerita selesai disusun dalam {elapsed_so_far} detik!")
            logger.info(f"[PERENCANA::JUDUL] Saya usulkan judul: \"{draft_title}\"")
            logger.info(f"[PERENCANA::TEMA] Tema yang diangkat: {theme}")
            logger.info(f"[PERENCANA::TARGET] Sasaran pembaca usia {target_age} | Gaya cerita: {story_style} | Nada emosi: {emotional_tone}")
            if learning_objectives:
                logger.info(f"[PERENCANA::TUJUAN] Tujuan pembelajaran yang ingin dicapai: {learning_objectives}")
            logger.info(f"[PERENCANA::PANJANG] Perkiraan panjang cerita: {story_length_result} | Gaya narasi: {narrative_style}")
            logger.info("[PERENCANA::OUTLINE] Ini alur cerita yang sudah saya rancang:")
            logger.info(f"[PERENCANA::OUTLINE]   Pembukaan → {outline['introduction']}")
            logger.info(f"[PERENCANA::OUTLINE]   Konflik   → {outline['conflict']}")
            logger.info(f"[PERENCANA::OUTLINE]   Klimaks   → {outline['climax']}")
            logger.info(f"[PERENCANA::OUTLINE]   Resolusi  → {outline['resolution']}")
            logger.info(f"[PERENCANA::TOKOH] Saya rancang {len(characters)} tokoh untuk cerita ini:")
            for i, char in enumerate(characters, 1):
                logger.info(f"[PERENCANA::TOKOH]   Tokoh {i}, peran: {char['role']}, usia: {char['age']}, kepribadian: {char['personality']}")
            logger.info(f"[PERENCANA::MORAL] Pesan moral yang ingin saya sampaikan lewat cerita ini: {moral}")
            _writer_label_map = {
                "writer_text":     "Sang Penulis (teks)",
                "writer_diagram":  "Data Visualizer (diagram)",
                "writer_image":    "Ilustrator (gambar)",
                "writer_director": "Sutradara (skrip)",
            }
            writer_labels = [_writer_label_map.get(w, w) for w in active_writers]
            logger.info(f"[PERENCANA::TIM] Tim penulis yang akan saya tugaskan: {', '.join(writer_labels)}")
            if result.writer_reasoning:
                logger.info(f"[PERENCANA::TIM] Alasan pemilihan tim ini: {result.writer_reasoning}")

        except Exception as e:
            logger.error(f"[PERENCANA::GALAT] Ada masalah saat menyusun rencana cerita: {e}")
            logger.warning("[PERENCANA::FALLBACK] Saya pakai rencana cadangan dulu agar proses tetap bisa lanjut...")

            sys_lang = LanguageConfig.SYSTEM_LANGUAGE
            is_en = sys_lang == "en"

            # Fallback values
            theme = user_message
            target_age = requested_target_age or "15-18"
            learning_objectives = ""
            story_style = "narrative" if is_en else "naratif"
            narrative_style = "mixed" if is_en else "campuran"
            emotional_tone = "warm" if is_en else "hangat"
            setting_ideas = ""
            character_ideas = ""
            if is_en:
                outline = {"introduction": "Introduction", "conflict": "Conflict", "climax": "Climax", "resolution": "Resolution"}
                characters = [{"name": "Main Character", "age": "10", "personality": "kind", "role": "protagonist"}]
                moral = "Lesson from the story"
            else:
                outline = {"introduction": "Pembukaan", "conflict": "Konflik", "climax": "Klimaks", "resolution": "Resolusi"}
                characters = [{"name": "Karakter Utama", "age": "10", "personality": "baik hati", "role": "protagonis"}]
                moral = "Pelajaran dari cerita"
            active_writers = ["text"]
            story_length_result = story_length
            draft_title = "Cerita Edukatif" if not is_en else "Educational Story"
            plan_text = "Fallback plan"

        # Notes:
        # - Span tracking handles overall latency/success
        # - log_generation above handles input/output/metadata tracking
        # - structured output parsing handled by Pydantic

        if self.langfuse and plan_span_id:
            elapsed_time = time.time() - start_time
            self.langfuse.end_span(
                span_id=plan_span_id,
                output_data={
                    "theme": theme,
                    "target_age": target_age,
                    "story_style": story_style,
                    "story_length": story_length_result,
                    "character_count": len(characters),
                    "active_writers": active_writers,
                    "chars": {"output_chars": len(plan_text)},
                    "elapsed_time_seconds": round(elapsed_time, 2),
                }
            )

        # Return unified state update with ALL parsed params + story plan
        return {
            # Parsed request params
            "theme": theme,
            "target_age": target_age,
            "learning_objectives": learning_objectives,
            "story_style": story_style,
            "narrative_style": narrative_style,
            "emotional_tone": emotional_tone,
            "user_characters": setting_ideas,  # Map to existing field
            "user_setting": character_ideas,  # Map to existing field
            "story_length": story_length_result,
            "enriched_context": f"Theme: {theme}\nStyle: {story_style}\nTone: {emotional_tone}\nLength: {story_length_result}",
            # Story plan
            "story_outline": outline,
            "characters": characters,
            "moral_message": moral,
            # Planner decision
            "active_writers": active_writers,
            "draft_title": draft_title,
            # Workflow
            "current_stage": "research",  # Next: research
            "messages": [{"role": "planner", "content": plan_text}],
            "_parsed": True
        }
