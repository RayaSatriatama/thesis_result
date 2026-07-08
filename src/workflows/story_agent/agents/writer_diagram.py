"""
Writer Diagram Agent - Generates educational diagrams using Mermaid
Uses MermaidChart MCP server for PNG rendering

Agent ini membuat diagram edukasi (concept maps, flowcharts, dll)
berdasarkan story outline dan research notes.
"""

import os
import subprocess
import time
import tempfile
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from ..state import StoryState
from settings import ModelConfig, LanguageConfig
from ..prompts import get_registry
from providers.llm_factory import get_llm_for_agent


# === PYDANTIC MODELS FOR STRUCTURED OUTPUT ===

class DiagramPlan(BaseModel):
    """Plan for diagram generation"""
    diagram_type: str = Field(
        description="Tipe diagram: flowchart, mindmap, sequence, classDiagram, atau stateDiagram"
    )
    title: str = Field(description="Diagram title" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Judul diagram")
    main_concept: str = Field(description="Main concept depicted" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Konsep utama yang digambarkan")
    key_elements: List[str] = Field(description="Key elements in diagram" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Elemen-elemen kunci dalam diagram")
    relationships: List[str] = Field(description="Relationships (A --> B)" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Hubungan antar elemen (format: A --> B)")
    mermaid_code: str = Field(description="Kode Mermaid lengkap untuk diagram")


# Import Langfuse for observability
try:
    from ..integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None


class WriterDiagramAgent:
    """
    Agent untuk menghasilkan diagram edukasi dari story.
    
    Menganalisis story outline dan research notes untuk membuat
    diagram yang membantu visualisasi konsep pembelajaran.
    
    Output: Mermaid code dan PNG image path.
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        credentials=None,
        project=None,
        output_dir: Optional[str] = None
    ):
        """
        Initialize WriterDiagramAgent.
        
        Args:
            model_name: Override model name
            credentials: Google service account credentials
            project: Google Cloud project ID
            output_dir: Directory to save generated diagram images
        """
        if output_dir is None:
            is_serverless = bool(
                os.getenv("VERCEL")
                or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
                or os.getenv("LAMBDA_TASK_ROOT")
            )
            output_dir = (
                os.path.join(tempfile.gettempdir(), "skripsi", "generated_images")
                if is_serverless
                else "data/generated_images"
            )
        self.output_dir = output_dir
        self.credentials = credentials
        self.project = project
        
        # Initialize LLM via provider-agnostic factory
        self.llm = get_llm_for_agent("diagram", model_name=model_name)
        
        # Langfuse for observability
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"[DIAGRAM::MEMULAI] Direktori output siap: {self.output_dir}")
    
    def _sanitize_mermaid_code(self, code: str) -> str:
        """
        Sanitize Mermaid code to prevent syntax errors with special characters.
        Ports logic from frontend MermaidRenderer to backend.
        """
        import re
        
        def safe_quote(content):
            """Escape special characters and ensure content is quoted."""
            content = content.replace('\n', ' ').strip()
            
            # Strip surrounding quotes if present
            if (content.startswith('"') and content.endswith('"')) or \
               (content.startswith("'") and content.endswith("'")):
                if len(content) >= 2:
                    content = content[1:-1]
            
            # Escape characters that break Mermaid labels
            content = content.replace('"', '#quot;')
            content = content.replace('(', '#40;')
            content = content.replace(')', '#41;')
            content = content.replace('[', '#91;')
            content = content.replace(']', '#93;')
            content = content.replace('{', '#123;')
            content = content.replace('}', '#125;')
            
            return f'"{content}"'

        clean_code = code
        
        # Regex patterns for common node types (Longer delimiters first)
        patterns = [
            (r'(\[\[)(.*?)(\]\])', '[', ']'),      # [[...]]
            (r'(\[\()(.*?)(\)\])', '[(', ')]'),   # [(...)]
            (r'(\(\()(.*?)(\)\))', '((', '))'),    # ((...))
            (r'(\{\{)(.*?)(\}\})', '{{', '}}'),    # {{...}}
            (r'(\[\/)(.*?)(\/\])', '[/', '/]'),    # [/.../]
            (r'(\[\\)(.*?)(\\\])', '[\\', '\\]'),  # [\...]
            (r'(\>)(.*?)(\])', '>', ']'),          # >...] (asymmetric)
            
            # Standard single char delimiters
            (r'(\[)([^\[\]\n]+?)(\])', '[', ']'),  # [...]
            (r'(\()([^\(\)\n]+?)(\))', '(', ')'),  # (...)
            (r'(\{)([^\{\}\n]+?)(\})', '{', '}'),  # {...}
        ]
        
        for regex_pattern, _, _ in patterns:
            # Use regex substitution with a callback function
            # We target group 2 (the content) to sanitize it
            def replacement_func(match):
                prefix = match.group(1) or ""
                content = match.group(2) or ""
                suffix = match.group(3) or ""
                
                # Check if it looks like a subgraph or class def which shouldn't be quoted
                # (Simple heuristic: if content has no spaces and is CamelCase, maybe leave it? 
                # But safest is to quote labels. IDs usually aren't inside brackets like this in modern syntax?
                # Actually x[id] is invalid, x[label] is valid.
                # So anything inside these brackets IS a label.)
                
                return f"{prefix}{safe_quote(content)[1:-1]}{suffix}"
                
            clean_code = re.sub(regex_pattern, replacement_func, clean_code)
            
        return clean_code
    def _generate_diagram_plan(self, state: StoryState) -> Optional[DiagramPlan]:
        """
        Generate diagram plan using structured output.
        
        Analyzes story content to determine best diagram type and structure.
        """
        logger.info("[DIAGRAM::BERPIKIR] Saya cermati dulu materi ceritanya, lalu saya tentukan jenis dan struktur diagram yang paling cocok...")
        from langchain_core.messages import SystemMessage, HumanMessage
        
        theme = state.get("theme", "")
        outline = state.get("story_outline", {})
        research = state.get("research_notes", "")
        characters = state.get("characters", [])
        moral = state.get("moral_message", "")
        target_age = state.get("target_age", "")
        
        registry = get_registry()
        system_prompt = registry.get("writer_diagram_system")

        messages = []
        try:
            human_prompt = registry.get("writer_diagram").format(
                theme=theme,
                target_age=target_age,
                moral=moral,
                introduction=outline.get('introduction', 'N/A'),
                conflict=outline.get('conflict', 'N/A'),
                climax=outline.get('climax', 'N/A'),
                resolution=outline.get('resolution', 'N/A'),
                research=research if research else 'None',
                characters=', '.join([c.get('name', 'Unknown') for c in characters]) if characters else 'None'
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
        except KeyError as e:
            logger.error(f"[DIAGRAM::GALAT] Terjadi masalah saat memformat prompt diagram: {e}. Menggunakan prompt cadangan.")
            # Fallback: Create simple prompt manually to avoid crash
            fallback_prompt = f"Buat diagram edukasi tentang {theme}. Target usia: {target_age}. Story outline: {str(outline)}. Fokus: Simplifikasi."
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=fallback_prompt)
            ]
        except Exception as e:
            logger.error(f"[DIAGRAM::GALAT] Terjadi kesalahan tak terduga saat membuat prompt: {e}")
            return None
        
        try:
            structured_llm = self.llm.with_structured_output(DiagramPlan)
            result: DiagramPlan = structured_llm.invoke(messages)
            
            # Log generation
            if self.langfuse:
                self.langfuse.log_generation(
                    name="diagram_planning",
                    model=ModelConfig.GEMINI_MODEL,
                    input_text=human_prompt,
                    output_text=str(result.model_dump()),
                    metadata={"diagram_type": result.diagram_type, "title": result.title}
                )

            logger.info(f"[DIAGRAM::MERENCANAKAN] Rencana diagram siap! Jenis: {result.diagram_type} | Judul: \"{result.title}\" | {len(result.key_elements)} elemen kunci.")
            return result
        except Exception as e:
            logger.error(f"[DIAGRAM::GALAT] Gagal menyusun rencana diagram: {e}")
            return None
    
    def _fix_diagram_plan(self, original_plan: DiagramPlan, error_message: str) -> Optional[DiagramPlan]:
        """
        Attempt to fix diagram code based on error message.
        """
        logger.info(f"[DIAGRAM::MEMPERBAIKI] Ada masalah pada kode diagram sebelumnya, saya coba perbaiki. Pesan error: {error_message}")
        from langchain_core.messages import SystemMessage, HumanMessage
        registry = get_registry()
        
        original_code_clean = original_plan.mermaid_code.replace('```mermaid', '').replace('```', '').strip()
        
        combined_prompt = registry.get("writer_diagram_fix").format(
            original_code=original_code_clean,
            error_message=error_message
        )
        
        messages = [
            HumanMessage(content=combined_prompt)
        ]
        
        try:
            structured_llm = self.llm.with_structured_output(DiagramPlan)
            # We might want to pass the original plan values as hints? 
            # But structured output will regenerate them. That's fine.
            result: DiagramPlan = structured_llm.invoke(messages)
            
            logger.info(f"[DIAGRAM::MEMPERBAIKI] Kode diagram berhasil diperbaiki, siap dicoba lagi.")
            return result
        except Exception as e:
            logger.error(f"[DIAGRAM::GALAT] Upaya perbaikan diagram juga gagal: {e}")
            return None

    async def _render_mermaid_to_png(self, mermaid_code: str, session_id: str = "default", theme: str = "default") -> tuple[Optional[str], Optional[str]]:
        """
        Render Mermaid code to PNG using the vendor Mermaid tool.
        Returns: (output_path, error_message)
        """
        from ..integrations.vendor_mermaid import render_mermaid
        
        try:
            # Prepare output path
            output_filename = f"diagram_{session_id}_{int(time.time())}.png"
            output_dir = os.path.join(os.getcwd(), "public", "diagrams")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # Call vendor tool
            result = await render_mermaid(
                mermaid_code=mermaid_code,
                output_path=output_path,
                theme=theme,
                background_color="white"
            )
            
            if result.get("success"):
                # Return relative path for frontend
                return f"/diagrams/{output_filename}", None
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Mermaid rendering failed: {error_msg}")
                return None, error_msg
                
        except subprocess.TimeoutExpired:
            logger.warning("[DIAGRAM::WAKTU] Proses menggambar diagram terlalu lama dan habis waktu.")
            return None, "TimeoutExpired"
        except Exception as e:
            logger.error(f"[DIAGRAM::GALAT] Gagal menghasilkan file PNG: {e}")
            return None, str(e)
    
    async def generate_diagram(self, state: StoryState) -> Dict:
        """
        Main method untuk generate educational diagram dari story.
        
        Dipanggil oleh LangGraph workflow sebagai salah satu parallel writer.
        
        Args:
            state: Current StoryState dengan outline dan research
            
        Returns:
            Dict dengan draft_diagram dan diagram_image_path untuk update state
        """
        start_time = time.time()
        session_id = state.get("session_id", "unknown")
        revision_count = state.get("revision_count", 0)
        
        # Check if diagram writer is active
        active_writers = state.get("active_writers", ["text"])
        if "diagram" not in active_writers:
            logger.info("[DIAGRAM::LEWATI] Penulis diagram sedang istirahat (tidak aktif).")
            return {}
        
        # Check revision flag
        if revision_count > 0 and not state.get("needs_diagram_revision", False):
            logger.info("[DIAGRAM::LEWATI] Revisi diagram tidak diperlukan, melewati langkah ini.")
            return {}
        
        logger.info(f"[DIAGRAM::MULAI] Oke, saya mulai membuat diagram untuk cerita ini!")
        if state.get("theme"):
            logger.info(f"[DIAGRAM::MULAI] Topik cerita: {state.get('theme')}")
        if state.get("target_age"):
            logger.info(f"[DIAGRAM::MULAI] Sasaran usia pembaca: {state.get('target_age')}")
        
        # Start Langfuse span
        span_id = None
        if self.langfuse:
            span_id = self.langfuse.start_span(
                name="writer_diagram_agent",
                input_data={
                    "theme": state.get("theme", ""),
                    "session_id": session_id,
                    "revision_count": revision_count
                },
                metadata={"agent": "writer_diagram"}
            )
        
        try:
            # Generate diagram plan (Initial Attempt)
            plan = self._generate_diagram_plan(state)
            
            if not plan:
                logger.warning("[DIAGRAM::MERENCANAKAN] Saya tidak bisa menyusun rencana diagram yang valid, cerita ini akan dilanjutkan tanpa diagram.")
                return {
                    "draft_diagram": "",
                    "diagram_image_path": "",
                    "needs_diagram_revision": False
                }
            
            # Retry Loop for Rendering
            max_retries = 3
            current_plan = plan
            final_png_path = None
            last_error = None
            
            for attempt in range(max_retries):
                # Clean up code block markers
                mermaid_code = current_plan.mermaid_code.replace("```mermaid", "").replace("```", "").strip()
                
                logger.info(f"[DIAGRAM::MENGGAMBAR] Mencoba menghasilkan gambar, percobaan {attempt+1} dari {max_retries}...")
                png_path, error_msg = await self._render_mermaid_to_png(mermaid_code, session_id, theme="neutral")
                
                if png_path:
                    final_png_path = png_path
                    logger.success(f"[DIAGRAM::SELESAI] Berhasil menghasilkan diagram pada percobaan ke-{attempt+1}!")
                    break
                else:
                    last_error = error_msg
                    logger.warning(f"[DIAGRAM::MENGGAMBAR] Percobaan ke-{attempt+1} gagal: {error_msg}")
                    
                    if attempt < max_retries - 1:
                        fixed_plan = self._fix_diagram_plan(current_plan, error_msg)
                        if fixed_plan:
                            current_plan = fixed_plan
                        else:
                            logger.warning("[DIAGRAM::MEMPERBAIKI] Model tidak bisa memperbaiki kode diagram, saya hentikan percobaan.")
                            break
            
            elapsed = time.time() - start_time
            if final_png_path:
                logger.info(f"[DIAGRAM::MERINCIKAN] Jenis diagram : {current_plan.diagram_type}")
                logger.info(f"[DIAGRAM::MERINCIKAN] Judul diagram : \"{current_plan.title}\"")
                logger.info(f"[DIAGRAM::MERINCIKAN] Elemen kunci  : {len(current_plan.key_elements)} elemen")
                logger.info(f"[DIAGRAM::MERINCIKAN] Disimpan di   : {final_png_path}")
                logger.info(f"[DIAGRAM::MERINCIKAN] Waktu render  : {round(elapsed, 2)} detik")
            else:
                logger.error(f"[DIAGRAM::GAGAL] Semua {max_retries} percobaan render gagal. Error terakhir: {last_error}")

            # Log to Langfuse
            if self.langfuse and span_id:
                self.langfuse.end_span(
                    span_id=span_id,
                    output_data={
                        "diagram_type": current_plan.diagram_type,
                        "title": current_plan.title,
                        "has_png": bool(final_png_path),
                        "elapsed_time": round(elapsed, 2),
                        "retries": attempt + 1,
                        "final_error": last_error
                    }
                )
            
            return {
                "draft_diagram": current_plan.mermaid_code.replace("```mermaid", "").replace("```", "").strip(),
                "diagram_image_path": final_png_path or "",
                "diagram_title": current_plan.title,
                "needs_diagram_revision": False  # Reset flag after revision
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"[DIAGRAM::GALAT] Terjadi kesalahan tak terduga saat membuat diagram: {e}")
            
            if self.langfuse and span_id:
                self.langfuse.end_span(
                    span_id=span_id,
                    output_data={"error": str(e), "traceback": error_trace}
                )
            
            return {
                "draft_diagram": "",
                "diagram_image_path": "",
                "needs_diagram_revision": False
            }


# Alias for graph.py compatibility
async def generate_diagram(state: StoryState) -> Dict:
    """Wrapper function untuk dipanggil oleh LangGraph node."""
    agent = WriterDiagramAgent()
    return await agent.generate_diagram(state)
