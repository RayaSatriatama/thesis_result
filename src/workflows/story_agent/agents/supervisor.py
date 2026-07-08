"""
Supervisor Agent - Dynamic interactive router
Routes: new story generation, targeted modification, Q&A, and passthrough finalization.
"""

import time
from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import StoryState
from ..prompts import get_registry
from loguru import logger
from settings import LanguageConfig
from providers.llm_factory import get_llm_for_agent

# Import Langfuse for observability
try:
    from ..integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None

# Import LightRAG client (optional - used only for Q&A when state context is thin)
try:
    from ..integrations.lightrag_client import get_lightrag_client
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    get_lightrag_client = None


class SupervisorDecision(BaseModel):
    """Decision model for the supervisor agent"""
    next_step: Literal["planning", "research", "writing", "critique", "finalize", "qa_response", "director", "FINISH"] = Field(
        ...,
        description="Next routing target in the workflow"
    )
    reasoning: str = Field(
        ...,
        description="Explanation for this routing decision" if LanguageConfig.SYSTEM_LANGUAGE == "en"
                    else "Alasan untuk keputusan rute ini"
    )
    interaction_mode: Literal["generation", "modification", "qa"] = Field(
        default="generation",
        description="Type of interaction: new story generation, modification of existing, or Q&A"
    )
    direct_response: Optional[str] = Field(
        default=None,
        description="Complete Q&A answer text. Only populated when next_step == 'qa_response'."
    )
    modification_scope: Optional[str] = Field(
        default=None,
        description="What specifically to modify, e.g. 'ending', 'character:Budi', 'title', 'full'"
    )
    needs_text_revision: bool = Field(
        default=True,
        description="Whether the text writer should run. Only relevant when next_step == 'writing'."
    )
    needs_diagram_revision: bool = Field(
        default=False,
        description="Whether the diagram writer should run. Only relevant when next_step == 'writing'."
    )
    review_plan: bool = Field(
        default=False,
        description=(
            "Set True only when the user explicitly requests to review, evaluate, or approve the plan "
            "before writing begins (e.g. 'tunjukkan rencananya dulu', 'saya mau review outlinenya', "
            "'minta persetujuan sebelum lanjut'). Default is False — planning runs straight to research."
        )
    )
    custom_plan: Optional[List[str]] = Field(
        default=None,
        description="Optional custom sequence of workflow step names to execute in a Plan-and-Execute sequence. E.g. ['research', 'planning', 'writing', 'critique']"
    )
    use_deepseek: bool = Field(
        default=False,
        description="Set True only if the user explicitly requested to use the DeepSeek model for this interaction."
    )


class SupervisorAgent:
    """Chief Supervisor: dynamic router for generation, modification, and Q&A."""

    def __init__(self, model_name: str = None, credentials=None, project=None):
        # credentials/project kept for backward-compat but ignored when provider != google_vertexai
        self.llm = get_llm_for_agent("supervisor", model_name=model_name)
        self.structured_llm = self.llm.with_structured_output(SupervisorDecision)
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None

    # ------------------------------------------------------------------
    # Internal tool methods (no external LLM cost)
    # ------------------------------------------------------------------

    def _read_story_context(self, state: StoryState) -> str:
        """Extract relevant content from the current state without any LLM call."""
        parts = []

        if state.get("final_story"):
            preview = state["final_story"][:400]
            parts.append(f"[CERITA FINAL — {len(state['final_story'])} kar.]\n{preview}...")
        elif state.get("draft_content"):
            preview = state["draft_content"][:400]
            parts.append(f"[DRAFT — {len(state['draft_content'])} kar.]\n{preview}...")

        if state.get("draft_title"):
            parts.append(f"Judul: {state['draft_title']}")

        if state.get("characters"):
            names = [c.get("name", "?") for c in state["characters"][:5]]
            parts.append(f"Tokoh: {', '.join(names)}")

        if state.get("moral_message"):
            parts.append(f"Pesan moral: {state['moral_message']}")

        if state.get("story_outline") and isinstance(state["story_outline"], dict):
            outline = state["story_outline"]
            parts.append(
                f"Outline: intro={bool(outline.get('introduction'))}, "
                f"conflict={bool(outline.get('conflict'))}, "
                f"resolution={bool(outline.get('resolution'))}"
            )

        if state.get("research_notes"):
            parts.append(f"Catatan riset (300 kar.): {state['research_notes'][:300]}...")

        if state.get("critique_feedback"):
            parts.append(f"Umpan balik kritik: {state['critique_feedback'][:200]}...")

        if state.get("hitl_feedback"):
            parts.append(f"[FEEDBACK MANUSIA]: {state['hitl_feedback']}")

        return "\n".join(parts) if parts else "Belum ada konten yang dihasilkan."

    async def _query_kg(self, query: str, state: StoryState) -> str:
        """
        Query LightRAG knowledge graph for factual context.
        Called only when state context is insufficient for the user's question.
        Returns empty string gracefully on any failure.
        """
        if not LIGHTRAG_AVAILABLE or get_lightrag_client is None:
            return ""
        try:
            language = state.get("language", "Indonesian")
            client = get_lightrag_client(language)
            is_available = await client.health_check()
            if not is_available:
                logger.debug("[SUPERVISOR::RISET] LightRAG sedang tidak tersedia, saya akan menjawab pertanyaan dari konteks state saja.")
                return ""
            result = await client.query_context_only(query, mode="hybrid", top_k=3)
            logger.debug(f"[SUPERVISOR::RISET] Saya mendapatkan {len(result)} karakter konteks dari knowledge graph untuk mendukung jawaban atas pertanyaan ini.")
            return result
        except Exception as e:
            logger.warning(f"[SUPERVISOR::RISET] Kueri knowledge graph gagal (tidak kritis, dilanjutkan tanpa konteks KG): {e}")
            return ""

    # ------------------------------------------------------------------
    # Main node method
    # ------------------------------------------------------------------

    async def decide(self, state: StoryState) -> Dict[str, Any]:
        """
        Analyze state and user message, then return a state patch dict.
        This is the LangGraph node function for the interactive workflow.
        """
        # --- Bypass shortcut: no LLM call, go straight to planning ---
        if state.get("bypass_supervisor"):
            logger.info("[SUPERVISOR::LEWATI] Saya melewati analisis, cerita baru dimulai langsung dari tahap perencanaan tanpa melewati saya.")
            return {
                "supervisor_next": "planning",
                "interaction_mode": "generation",
                "revision_count": 0,
                "bypass_supervisor": False,
            }

        is_en = LanguageConfig.SYSTEM_LANGUAGE == "en"
        user_message = state.get("user_message", "")
        has_content = bool(state.get("final_story") or state.get("draft_content"))

        logger.info(
            "[SUPERVISOR::MULAI] Menganalisis permintaan untuk routing sebelum planner/agen lain "
            f"(panjang pesan: {len(user_message)} karakter)."
        )

        # --- Conditionally query KG for requests ---
        kg_context = ""
        story_context = self._read_story_context(state)
        # Only query KG if story content exists (knowledge already ingested) AND state context is thin
        if has_content and len(story_context) < 600:
            kg_context = await self._query_kg(user_message, state)

        # --- Build supervisor context message ---
        registry = get_registry()
        system_prompt = registry.get("supervisor")
        lang_note = (
            "\nIMPORTANT: Write the 'reasoning' field in English."
            if is_en else
            "\nPENTING: Tuliskan field 'reasoning' dalam Bahasa Indonesia."
        )

        prior_arch = state.get("prior_stories_archive") or []
        prior_block = ""
        if isinstance(prior_arch, list) and prior_arch:
            chunks = []
            for i, row in enumerate(prior_arch, start=1):
                if not isinstance(row, dict):
                    continue
                tit = str(row.get("title") or f"#{i}")
                ex = str(row.get("excerpt") or "").strip()
                if ex:
                    chunks.append(f"--- Arsip cerita #{i}: {tit} ---\n{ex}")
            if chunks:
                prior_block = (
                    "\n=== Cerita selesai sebelumnya (sesi UI ini; gunakan untuk recall, lanjutan, atau konsistensi tokoh/alur) ===\n"
                    + "\n\n".join(chunks)
                    + "\n"
                )

        chat_hist = state.get("user_chat_history") or []
        chat_block = ""
        if isinstance(chat_hist, list) and chat_hist:
            lines = []
            for turn in chat_hist[-16:]:
                if not isinstance(turn, dict):
                    continue
                r = str(turn.get("role") or "?")
                t = str(turn.get("text") or turn.get("content") or "").strip()
                if t:
                    lines.append(f"{r}: {t[:1200]}")
            if lines:
                chat_block = "\n=== Recent chat turns (same session) ===\n" + "\n".join(lines) + "\n"

        context_msg = f"""User Request: {user_message}
{prior_block}{chat_block}
=== Current State Summary ===
{story_context}

=== Workflow Metadata ===
current_stage: {state.get('current_stage', 'start')}
revision_count: {state.get('revision_count', 0)}
quality_score: {state.get('quality_score', 0.0)}
interaction_mode (previous): {state.get('interaction_mode', 'none')}
hitl_feedback: {state.get('hitl_feedback') or 'none'}
active_execution_plan (supervisor_plan): {state.get('supervisor_plan') or 'none'}
current_plan_index (supervisor_plan_index): {state.get('supervisor_plan_index', 0)}
"""
        if kg_context:
            context_msg += f"\n=== Knowledge Graph Context ===\n{kg_context}"

        messages = [
            SystemMessage(content=system_prompt + lang_note),
            HumanMessage(content=context_msg),
        ]

        # --- LLM call with Langfuse tracing ---
        start_time = time.time()
        span_id = None
        try:
            if self.langfuse:
                span_id = self.langfuse.start_span(
                    name="supervisor_agent",
                    input_data={
                        "user_message": user_message,
                        "current_stage": state.get("current_stage"),
                        "has_content": has_content,
                        "kg_queried": bool(kg_context),
                    },
                    metadata={"agent": "supervisor"}
                )

            response: SupervisorDecision = await self.structured_llm.ainvoke(messages)

            if not response:
                logger.warning("[SUPERVISOR::MEMUTUSKAN] LLM mengembalikan respons kosong, saya menggunakan keputusan cadangan: lanjutkan ke perencanaan.")
                response = SupervisorDecision(
                    next_step="planning",
                    reasoning="Parsing failed — defaulting to planning",
                    interaction_mode="generation",
                )

            # Check if AI decided to route to DeepSeek
            import os
            if response.next_step == "qa_response" and getattr(response, "use_deepseek", False):
                try:
                    ds_key = os.getenv("DEEPSEEK_API_KEY")
                    if ds_key:
                        logger.info("[SUPERVISOR::MEMUTUSKAN] Permintaan DeepSeek terdeteksi. Memanggil DeepSeek untuk menjawab...")
                        from providers.llm_factory import get_llm
                        ds_llm = get_llm(provider="deepseek", model_name="deepseek-chat", temperature=0.5)
                        
                        qa_prompt = f"""Peran: Kamu adalah "Kabi AI Agent", agen pendamping pembelajaran yang sabar dan membantu.
                        
Pertanyaan Pengguna:
{user_message}

Konteks Cerita/State saat ini:
{story_context}

Harap berikan respons mendalam, ramah, terstruktur dalam Bahasa Indonesia.
Respons harus ringkas, maksimal 2 paragraf!
WAJIB Format respons dalam HTML murni (tanpa Markdown, tanpa backticks).
Gunakan tag: <section>, <h3>, <p>, <ol>, <ul>, <li>, <strong>, <em>, <pre>, <code>.
Pisahkan setiap paragraf dengan tag <p> dan beri jarak <br>."""
                        
                        ds_res = await ds_llm.ainvoke(qa_prompt)
                        response.direct_response = ds_res.content
                    else:
                        logger.warning("[SUPERVISOR::MEMUTUSKAN] Pengguna meminta DeepSeek, tetapi DEEPSEEK_API_KEY tidak dikonfigurasi.")
                        response.direct_response = f"<p><em>(Catatan Supervisor: Layanan DeepSeek tidak terkonfigurasi pada server, permintaan dialihkan secara otomatis ke Kabi AI Agent berbasis Gemini/Default)</em></p><br>" + (response.direct_response or "")
                except Exception as ex:
                    logger.error(f"[SUPERVISOR::MEMUTUSKAN] Gagal memanggil DeepSeek: {ex}")
                    response.direct_response = f"<p><em>(Catatan Supervisor: Gagal menghubungi DeepSeek ({str(ex)}), dialihkan ke Gemini/Default)</em></p><br>" + (response.direct_response or "")

            # --- Build state patch ---
            patch: Dict[str, Any] = {
                "supervisor_next": response.next_step,
                "interaction_mode": response.interaction_mode,
            }

            if hasattr(response, "custom_plan") and response.custom_plan:
                patch["supervisor_plan"] = response.custom_plan
                patch["supervisor_plan_index"] = 0
                logger.info(f"[SUPERVISOR::PLAN] Rencana baru diformulasikan oleh AI: {response.custom_plan}")
            else:
                existing_plan = state.get("supervisor_plan") or []
                if existing_plan and response.next_step in existing_plan:
                    next_idx = existing_plan.index(response.next_step)
                    patch["supervisor_plan"] = existing_plan
                    patch["supervisor_plan_index"] = next_idx
                    logger.info(f"[SUPERVISOR::PLAN] AI melanjutkan langkah berikut dari rencana: «{response.next_step}» (Indeks: {next_idx})")
                else:
                    patch["supervisor_plan"] = []
                    patch["supervisor_plan_index"] = 0

            if response.direct_response:
                patch["supervisor_response"] = response.direct_response

            if response.modification_scope:
                patch["modification_scope"] = response.modification_scope

            if response.next_step == "writing":
                patch["needs_text_revision"] = response.needs_text_revision
                patch["needs_diagram_revision"] = response.needs_diagram_revision

            # Propagate plan review request (default False)
            patch["review_plan"] = response.review_plan
            # Jangan biarkan checkpoint lama mempertahankan bypass_supervisor=True
            patch["bypass_supervisor"] = False

            # Reset generation state when starting a brand-new story
            if response.interaction_mode == "generation" and response.next_step == "planning":
                patch.update({
                    "revision_count": 0,
                    "final_story": "",
                    "draft_content": "",
                    "draft_title": "",
                    "story_outline": {},
                    "characters": [],
                    "research_notes": "",
                    "critique_feedback": "",
                    "supervisor_response": "",
                })

            # Clear consumed hitl_feedback
            if state.get("hitl_feedback"):
                patch["hitl_feedback"] = ""

            logger.info(
                f"[SUPERVISOR::MEMUTUSKAN] Saya memutuskan: {response.next_step} "
                f"(mode: {response.interaction_mode}) — alasan: {response.reasoning}"
            )

            if self.langfuse:
                formatted_input = "\n\n".join(
                    f"[{msg.__class__.__name__}]\n{msg.content}"
                    for msg in messages
                )
                self.langfuse.log_generation(
                    name="supervisor_decision",
                    model=self.llm.model_name,
                    input_text=formatted_input,
                    output_text=f"next_step: {response.next_step}\nmode: {response.interaction_mode}\nreasoning: {response.reasoning}",
                    metadata={"reasoning": response.reasoning}
                )
                if span_id:
                    self.langfuse.end_span(
                        span_id=span_id,
                        output_data={
                            "decision": response.next_step,
                            "interaction_mode": response.interaction_mode,
                            "elapsed_time_seconds": round(time.time() - start_time, 2),
                        }
                    )

            return patch

        except Exception as e:
            logger.error(f"[SUPERVISOR::GAGAL] Saya tidak bisa menyelesaikan analisis dan pengambilan keputusan, alasan: {e}. Mengarahkan ke perencanaan sebagai langkah aman.")
            if self.langfuse and span_id:
                self.langfuse.end_span(span_id=span_id, output_data={"error": str(e)})
            return {
                "supervisor_next": "planning",
                "interaction_mode": "generation",
                "bypass_supervisor": False,
            }

    # ------------------------------------------------------------------
    # Backward-compat method (used as conditional edge reader)
    # ------------------------------------------------------------------

    async def route(self, state: StoryState) -> str:
        """
        Backward-compatible thin wrapper.
        If supervisor_next is already set in state, return it directly.
        Otherwise call decide() and return the routing string.
        NOTE: In the interactive workflow use decide() as the node function instead.
        """
        next_step = state.get("supervisor_next")
        if next_step:
            return next_step
        patch = await self.decide(state)
        return patch.get("supervisor_next", "planning")

