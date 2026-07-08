"""
Image Generator Agent - Menghasilkan ilustrasi untuk cerita menggunakan Gemini 2.5 Flash Image.

Agent ini berjalan secara paralel dengan CriticAgent setelah WriterAgent selesai.
Menggunakan google-genai SDK untuk text-to-image generation.
"""

import base64
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

from loguru import logger
from google import genai
from google.oauth2 import service_account
from pydantic import BaseModel, Field

from ..state import StoryState
from ..state import StoryState
from ..utils.retry import is_rate_limit_error
from ..prompts import get_registry
from settings import LanguageConfig

# Import Langfuse for observability
try:
    from ..integrations.langfuse_client import get_langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    def get_langfuse():
        return None


# Pydantic models untuk structured output
class ImagePrompt(BaseModel):
    """Single image generation prompt."""
    scene_description: str = Field(description="Visual description of the scene" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Deskripsi visual detail dari adegan")
    characters_present: List[str] = Field(description="Characters in the scene" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Karakter yang muncul di adegan")
    emotional_mood: str = Field(description="Emotional mood" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Suasana emosional (ceria, tegang, misterius, dll)")
    setting_details: str = Field(description="Setting and time details" if LanguageConfig.SYSTEM_LANGUAGE == "en" else "Detail latar tempat dan waktu")


class ImageGenerationPlan(BaseModel):
    """Plan untuk generating images dari cerita."""
    scenes_to_illustrate: List[ImagePrompt] = Field(
        description="Daftar scene penting yang perlu diilustrasikan",
        min_length=1,
        max_length=3
    )
    overall_art_style: str = Field(
        description="Gaya seni keseluruhan (cartoon, watercolor, digital art, dll)"
    )
    color_palette: str = Field(
        description="Palet warna dominan"
    )


def _split_data_url_if_any(value: str) -> tuple[str, Optional[str]]:
    """
    OpenRouter returns image_url.url as a full data URL (data:image/png;base64,...).
    Gemini stores raw base64 only. Normalize to (raw_base64, mime) for a single client contract.
    """
    s = (value or "").strip()
    if not s:
        return ("", None)
    if not s.startswith("data:"):
        return (s, None)
    try:
        head, b64 = s.split(",", 1)
        mime = head[5:].split(";")[0].strip() or "image/png"
        return (b64, mime)
    except ValueError:
        return (s, None)


class GeneratedImage(BaseModel):
    """Hasil image generation."""
    image_id: str = Field(description="Unique identifier untuk image")
    scene_index: int = Field(description="Index scene dari cerita")
    prompt_used: str = Field(description="Prompt yang digunakan untuk generate")
    file_path: Optional[str] = Field(default=None, description="Path ke file image")
    base64_data: Optional[str] = Field(default=None, description="Base64 encoded image data")
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type when base64_data is raw (e.g. image/png); omit if base64_data is itself a data URL",
    )
    generation_time: float = Field(description="Waktu generate dalam detik")
    success: bool = Field(description="Apakah generation berhasil")
    error_message: Optional[str] = Field(default=None, description="Error message jika gagal")


class ImageGeneratorAgent:
    """
    Agent untuk menghasilkan ilustrasi dari cerita.

    Menggunakan Gemini 2.5 Flash Image untuk text-to-image generation.
    Berjalan paralel dengan CriticAgent setelah Writer selesai.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        credentials: Optional[service_account.Credentials] = None,
        project: Optional[str] = None,
        output_dir: Optional[str] = None,
        num_images: int = 1,
        aspect_ratio: str = "16:9"
    ):
        """
        Initialize ImageGeneratorAgent.

        Args:
            model_name: Override model name
            credentials: Google service account credentials (not used for Gemini API)
            project: Google Cloud project ID (not used for Gemini API)
            output_dir: Directory untuk menyimpan generated images
            num_images: Jumlah gambar yang akan di-generate (default: 1)
            aspect_ratio: Aspect ratio gambar (1:1, 16:9, 9:16, 4:3, 3:4)
        """
        self.credentials = credentials
        self.project = project
        import os
        import tempfile

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
        self.output_dir = Path(output_dir)
        self.num_images = num_images
        self.aspect_ratio = aspect_ratio

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Gemini client
        self._init_client()

        # Model untuk image generation (Gemini 2.5 Flash Image)
        self.image_model = "google/gemini-2.5-flash-image" if getattr(self, "is_openrouter", False) else "gemini-2.5-flash-image"
        self.text_model = "gemini-2.5-flash"  # For planning prompts

        # Initialize Langfuse
        self.langfuse = get_langfuse() if LANGFUSE_AVAILABLE else None

    def _init_client(self):
        """Initialize Google Gemini API client or OpenRouter."""
        self.is_openrouter = False
        try:
            or_key = os.environ.get("OPENROUTER_API_KEY")
            if or_key:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=or_key,
                    default_headers={"HTTP-Referer": "http://localhost:8000"}
                )
                self.is_openrouter = True
                logger.success(f"[GAMBAR::PENGATURAN] Saya berhasil terhubung ke OpenRouter, siap melukis ilustrasi untuk cerita.")
                return

            # Default fallback to Gemini GenAI SDK
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

            if api_key:
                self.client = genai.Client(api_key=api_key)
                logger.success(f"[GAMBAR::PENGATURAN] Saya berhasil terhubung ke Gemini, siap melukis ilustrasi untuk cerita.")
            else:
                logger.warning(f"[GAMBAR::PENGATURAN] Klien API Gambar tidak ditemukan, ilustrasi tidak bisa dilukis.")
                self.client = None

        except Exception as e:
            logger.warning(f"[GAMBAR::PENGATURAN] Gagal terhubung ke Klien API Gambar: {e}")
            self.client = None

    def _create_image_prompt(
        self,
        scene: ImagePrompt,
        art_style: str,
        color_palette: str,
        target_age: str = "15-18"
    ) -> str:
        """
        Buat prompt yang optimal untuk image generation.

        Args:
            scene: Deskripsi scene
            art_style: Gaya seni
            color_palette: Palet warna
            target_age: Target usia pembaca
        """
        # Tentukan style berdasarkan target age
        age_style_map = {
            "5-7": "cute, simple, child-friendly cartoon style",
            "8-10": "colorful, detailed children's book illustration style",
            "11-13": "dynamic, semi-realistic illustration style",
            "14-17": "detailed, modern digital art style",
            "18+": "sophisticated, artistic illustration style"
        }

        age_style = age_style_map.get(target_age, "colorful, detailed children's book illustration style")

        registry = get_registry()
        prompt = registry.get("image_gen_style").format(
            scene_description=scene.scene_description,
            characters=', '.join(scene.characters_present) if scene.characters_present else 'No specific characters',
            emotional_mood=scene.emotional_mood,
            setting_details=scene.setting_details,
            art_style=art_style,
            age_style=age_style,
            color_palette=color_palette
        )

        return prompt

    def _extract_scenes_from_story(self, story_content: str, characters: List[Dict]) -> List[ImagePrompt]:
        """
        Extract key scenes from story untuk diilustrasikan.

        Uses Gemini text model dengan structured output untuk analisis scene.
        """
        if not self.client:
            # Fallback: buat scene sederhana
            return [
                ImagePrompt(
                    scene_description="Main scene from the story",
                    characters_present=[c.get("name", "character") for c in characters[:2]] if characters else ["Character"],
                    emotional_mood="engaging and colorful",
                    setting_details="The story's main setting"
                )
            ]

        try:
            # Prepare character info
            char_names = [c.get("name", "Unknown") for c in characters] if characters else ["Main character"]

            registry = get_registry()
            prompt = registry.get("image_gen_scenes").format(
                num_images=self.num_images,
                story_content=story_content, # Full content
                characters=', '.join(char_names)
            )

            # Use structured output via google-genai SDK

            # Use structured output via google-genai SDK
            from google.genai.types import GenerateContentConfig

            response = self.client.models.generate_content(
                model=self.text_model,
                contents=[prompt],
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ImageGenerationPlan
                )
            )

            # Log generation for scene extraction
            if self.langfuse:
                self.langfuse.log_generation(
                    name="image_scene_extraction",
                    model=self.text_model,
                    input_text=prompt,
                    output_text=response.text,
                    metadata={"num_scenes_requested": self.num_images}
                )

            # Parse response using Pydantic
            import json
            plan = ImageGenerationPlan.model_validate_json(response.text)

            # Limit to num_images
            scenes = plan.scenes_to_illustrate[:self.num_images]
            logger.debug(f"[GAMBAR::MERENCANAKAN] Saya sudah mengidentifikasi {len(scenes)} adegan penting dari cerita yang akan dilukis.")
            return scenes

        except Exception as e:
            logger.warning(f"[GAMBAR::MERENCANAKAN] Analisis adegan terstruktur gagal, saya akan melanjutkan dengan rencana cadangan. Alasan: {e}")
            # Fallback scene
            return [
                ImagePrompt(
                    scene_description="Main scene from the story",
                    characters_present=[c.get("name", "character") for c in characters[:2]] if characters else ["Character"],
                    emotional_mood="engaging and colorful",
                    setting_details="The story's main setting"
                )
            ]

    def _generate_single_image(
        self,
        prompt: str,
        scene_index: int,
        session_id: str
    ) -> GeneratedImage:
        """
        Generate satu image dari prompt menggunakan Gemini 2.5 Flash Image.

        Returns:
            GeneratedImage dengan hasil atau error
        """
        import time
        start_time = time.time()

        image_id = f"{session_id}_{scene_index}_{uuid.uuid4().hex[:8]}"

        if not getattr(self, "client", None):
            return GeneratedImage(
                image_id=image_id,
                scene_index=scene_index,
                prompt_used=prompt,
                generation_time=time.time() - start_time,
                success=False,
                error_message="API client not initialized"
            )

        try:
            if getattr(self, "is_openrouter", False):
                # OpenRouter: gunakan modalities dan ambil gambar dari field images
                response = self.client.chat.completions.create(
                    model=self.image_model,
                    messages=[{"role": "user", "content": prompt}],
                    modalities=["image", "text"],
                    timeout=60.0
                )
                message = response.choices[0].message
                base64_data = None
                if hasattr(message, "images") and message.images:
                    # Ambil base64 dari image_url.url (biasanya data URL lengkap dari OpenRouter)
                    image_url = message.images[0]["image_url"]["url"] if isinstance(message.images[0], dict) else message.images[0].image_url.url
                    raw_b64, mime = _split_data_url_if_any(image_url)
                    base64_data = raw_b64 or None
                    mime_type = mime
                else:
                    base64_data = None
                    mime_type = None
                return GeneratedImage(
                    image_id=image_id,
                    scene_index=scene_index,
                    prompt_used=prompt,
                    file_path=None,
                    base64_data=base64_data,
                    mime_type=mime_type,
                    generation_time=time.time() - start_time,
                    success=base64_data is not None,
                    error_message=None if base64_data else "No image returned in OpenRouter response"
                )

            # Generate image using Gemini 2.5 Flash Image natively
            response = self.client.models.generate_content(
                model=self.image_model,
                contents=[prompt]
            )

            # Log generation for image call
            if self.langfuse:
                self.langfuse.log_generation(
                    name="image_generation_call",
                    model=self.image_model,
                    input_text=prompt,
                    output_text="Image generated successfully" if response.candidates else "No candidates",
                    metadata={
                        "scene_index": scene_index,
                        "session_id": session_id,
                        "image_id": image_id
                    }
                )

            # Extract image from response
            image_found = False
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    # Get image data
                    image_data = part.inline_data.data
                    mime_type = part.inline_data.mime_type

                    # Determine file extension
                    ext_map = {
                        "image/png": ".png",
                        "image/jpeg": ".jpg",
                        "image/webp": ".webp"
                    }
                    ext = ext_map.get(mime_type, ".png")

                    # Save to file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"story_illustration_{timestamp}_{scene_index}{ext}"
                    file_path = self.output_dir / filename

                    # Decode and save
                    if isinstance(image_data, str):
                        image_bytes = base64.b64decode(image_data)
                    else:
                        image_bytes = image_data

                    with open(file_path, "wb") as f:
                        f.write(image_bytes)

                    # Also keep base64 for streaming/display
                    if isinstance(image_data, bytes):
                        b64_data = base64.b64encode(image_data).decode()
                    else:
                        b64_data = image_data

                    image_found = True
                    return GeneratedImage(
                        image_id=image_id,
                        scene_index=scene_index,
                        prompt_used=prompt,
                        file_path=str(file_path),
                        base64_data=b64_data,
                        mime_type=mime_type,
                        generation_time=time.time() - start_time,
                        success=True
                    )

            # No image in response
            if not image_found:
                return GeneratedImage(
                    image_id=image_id,
                    scene_index=scene_index,
                    prompt_used=prompt,
                    generation_time=time.time() - start_time,
                    success=False,
                    error_message="No image in response"
                )

        except Exception as e:
            error_msg = str(e)

            # Check for rate limit
            if is_rate_limit_error(e):
                error_msg = f"Rate limit exceeded: {error_msg}"

            return GeneratedImage(
                image_id=image_id,
                scene_index=scene_index,
                prompt_used=prompt,
                generation_time=time.time() - start_time,
                success=False,
                error_message=error_msg
            )

        # Fallback return (should never reach here due to if/return/except above)
        return GeneratedImage(
            image_id=image_id,
            scene_index=scene_index,
            prompt_used=prompt,
            generation_time=time.time() - start_time,
            success=False,
            error_message="Unknown error occurred"
        )

    def generate_illustrations(self, state: StoryState) -> Dict[str, Any]:
        """
        Main method untuk generate illustrations dari story.

        Dipanggil oleh LangGraph workflow, berjalan paralel dengan CriticAgent.

        Args:
            state: Current StoryState dengan draft_content dan characters

        Returns:
            Dict dengan generated_images untuk update state
        """
        # Check if image writer is active
        active_writers = state.get("active_writers", ["text"])
        if "image" not in active_writers:
            logger.info("[GAMBAR::LEWATI] Saya tidak ditugaskan untuk melukis ilustrasi kali ini, melewati proses penggambaran.")
            return {}

        # Check revision flag on subsequent passes
        revision_count = state.get("revision_count", 0)
        generated_already = state.get("generated_images", [])

        # Only skip if we have images AND don't need revision
        if revision_count > 0 and generated_already and not state.get("needs_image_revision", False):
            logger.info(f"[GAMBAR::LEWATI] Ilustrasi sudah ada dari putaran sebelumnya dan tidak perlu direvisi, saya menggunakan gambar yang sudah ada ({len(generated_already)} gambar).")
            return {}

        import time
        start_time = time.time()

        # Get story content
        story_content = state.get("draft_content", "")
        characters = state.get("characters", [])
        target_age = state.get("target_age", "15-18")
        session_id = state.get("session_id", f"session_{uuid.uuid4().hex[:8]}")
        theme = state.get("theme", "adventure")

        logger.info(f"[GAMBAR::MULAI] Saya mulai melukis ilustrasi, tema: {theme}, usia target: {target_age}, panjang cerita: {len(story_content)} karakter, jumlah gambar: {self.num_images}.")

        # Start Langfuse span
        span_id = None
        if self.langfuse:
            span_id = self.langfuse.start_span(
                name="image_generator_agent",
                input_data={
                    "theme": theme,
                    "target_age": target_age,
                    "story_length_chars": len(story_content),
                    "revision_count": revision_count
                },
                metadata={"agent": "image_generator"}
            )

        if not story_content:
            logger.warning("[GAMBAR::PERINGATAN] Cerita belum tersedia, saya tidak bisa melukis ilustrasi tanpa konten cerita.")
            return {"generated_images": []}

        # Determine art style based on theme
        theme_style_map = {
            "adventure": ("vibrant digital art", "bold primary colors"),
            "fantasy": ("magical watercolor", "mystical purples and blues"),
            "science": ("clean modern illustration", "cool blues and greens"),
            "nature": ("soft watercolor", "natural greens and browns"),
            "friendship": ("warm cartoon style", "warm oranges and yellows"),
            "family": ("heartwarming illustration", "soft pastels"),
            "mystery": ("atmospheric digital art", "deep shadows with highlights"),
        }

        art_style, color_palette = theme_style_map.get(
            theme.lower() if theme else "adventure",
            ("colorful children's book illustration", "bright and cheerful colors")
        )

        # Extract key scenes
        logger.info(f"[GAMBAR::MENGANALISIS] Saya membaca cerita dan memilih adegan-adegan penting yang layak dilukis sebagai ilustrasi.")
        scenes = self._extract_scenes_from_story(story_content, characters)

        # Generate images for each scene
        generated_images = []
        for i, scene in enumerate(scenes):
            logger.info(f"[GAMBAR::MENGGAMBAR] Melukis ilustrasi {i+1} dari {len(scenes)}, suasana: {scene.emotional_mood}, latar: {scene.setting_details}.")

            # Create optimized prompt
            prompt = self._create_image_prompt(
                scene=scene,
                art_style=art_style,
                color_palette=color_palette,
                target_age=target_age
            )

            # Generate image
            result = self._generate_single_image(
                prompt=prompt,
                scene_index=i,
                session_id=session_id
            )

            generated_images.append(result.model_dump())

            if result.success:
                logger.success(f"[GAMBAR::SELESAI] Ilustrasi {i+1} selesai dilukis dalam {result.generation_time:.1f}s, disimpan di: {result.file_path}")
            else:
                logger.warning(f"[GAMBAR::GAGAL] Ilustrasi {i+1} gagal dilukis, alasan: {result.error_message}")

        # Summary
        elapsed = time.time() - start_time
        success_count = sum(1 for img in generated_images if img.get("success"))

        # End Langfuse span
        if self.langfuse and span_id:
            self.langfuse.end_span(
                span_id=span_id,
                output_data={
                    "generated_images_count": len(generated_images),
                    "success_count": success_count,
                    "generated_paths": [img.get("file_path") for img in generated_images if img.get("success")],
                    "elapsed_time_seconds": round(elapsed, 2)
                }
            )

        if success_count > 0:
            logger.success(f"[GAMBAR::SELESAI] Saya selesai melukis {success_count} dari {len(generated_images)} ilustrasi dalam {elapsed:.2f} detik.")
        else:
            logger.warning(f"[GAMBAR::GAGAL] Tidak ada ilustrasi yang berhasil dilukis dari {len(generated_images)} percobaan, semua gagal. Ilustrasi akan dilewati untuk sesi ini.")

        return {
            "generated_images": generated_images
        }


# Alias untuk compatibility dengan graph.py
def generate_images(state: StoryState) -> Dict[str, Any]:
    """
    Wrapper function untuk dipanggil oleh LangGraph node.
    """
    agent = ImageGeneratorAgent()
    return agent.generate_illustrations(state)
