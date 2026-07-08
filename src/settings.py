"""
Centralized Settings for Story-Based Learning AI
All configurable values in one place for easy tuning

Konfigurasi Terpusat untuk AI Pembelajaran Berbasis Cerita
Semua nilai yang dapat dikonfigurasi dalam satu tempat
"""

import os
from dotenv import load_dotenv
from loguru import logger

# Load .env file if exists
load_dotenv()


# =============================================================================
# SECURITY CONFIGURATION - Konfigurasi Keamanan
# =============================================================================

class SecurityConfig:
    """Konfigurasi untuk keamanan API"""

    # API Key for frontend-backend communication
    API_KEY = os.getenv("API_KEY", "")

    # Allowed CORS origins (comma-separated)
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")


# =============================================================================
# LLM PROVIDER CONFIGURATION - Konfigurasi Provider LLM
# =============================================================================

class LLMProviderConfig:
    """
    Konfigurasi provider LLM yang digunakan oleh semua agent.

    Provider yang didukung (LLM_PROVIDER):
      - "google_vertexai"  : Google Vertex AI (membutuhkan credential.json & project)
      - "google_genai"     : Google Generative AI API (membutuhkan GEMINI_API_KEY)
      - "openai"           : OpenAI API
      - "openrouter"       : OpenRouter (akses 200+ model via satu API key)
      - "deepseek"         : DeepSeek API (OpenAI-compatible)
      - "glm"              : Zhipu AI GLM (OpenAI-compatible)
      - "ollama"           : Ollama local server (OpenAI-compatible)
    """

    PROVIDER = os.getenv("LLM_PROVIDER", "google_vertexai")

    # ---- Generic (overrides provider default if set) ----
    MODEL = os.getenv("LLM_MODEL", "")        # fallback to provider default when empty
    API_KEY = os.getenv("LLM_API_KEY", "")     # generic API key slot

    # ---- Google ----
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_PROJECT  = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    # ---- OpenAI ----
    OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

    # ---- OpenRouter ----
    OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")  # optional, for rankings
    OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Story-Based Learning AI")

    # ---- DeepSeek ----
    DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ---- GLM / Zhipu AI ----
    GLM_API_KEY  = os.getenv("GLM_API_KEY") or os.getenv("ZHIPUAI_API_KEY", "")
    GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    # ---- Ollama ----
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    # ---- Custom OpenAI-compatible endpoint ----
    CUSTOM_BASE_URL = os.getenv("LLM_BASE_URL", "")

    @classmethod
    def is_google(cls) -> bool:
        """Apakah provider saat ini adalah Google (Vertex AI atau GenAI)?"""
        return cls.PROVIDER in ("google_vertexai", "google_genai")

    @classmethod
    def default_model(cls) -> str:
        """Model default berdasarkan provider jika LLM_MODEL tidak diset."""
        if cls.MODEL:
            return cls.MODEL
        defaults = {
            "google_vertexai": "gemini-2.5-flash",
            "google_genai":    "gemini-2.5-flash",
            "openai":          "gpt-4o-mini",
            "openrouter":      "openai/gpt-4o-mini",
            "deepseek":        "deepseek-chat",
            "glm":             "glm-4-flash",
            "ollama":          "llama3.2",
        }
        return defaults.get(cls.PROVIDER, "gemini-2.5-flash")


# =============================================================================
# MODEL CONFIGURATION - Konfigurasi Model AI
# =============================================================================

class ModelConfig:
    """Konfigurasi untuk model AI"""

    # Model name – baca dari LLMProviderConfig agar konsisten
    @classmethod
    def _model(cls) -> str:
        return LLMProviderConfig.default_model()

    # Kept for backward-compat: code that reads ModelConfig.GEMINI_MODEL still works
    GEMINI_MODEL = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Temperature settings per agent (0.0 = deterministic, 1.0 = creative)
    PARSER_TEMPERATURE = float(os.getenv("PARSER_TEMPERATURE", "0.3"))  # Parse user request
    RESEARCHER_TEMPERATURE = float(os.getenv("RESEARCHER_TEMPERATURE", "0.5"))  # Research agent
    PLANNER_TEMPERATURE = float(os.getenv("PLANNER_TEMPERATURE", "0.7"))  # Planning agent
    WRITER_TEMPERATURE = float(os.getenv("WRITER_TEMPERATURE", "0.9"))  # Writer agent (more creative)
    CRITIC_TEMPERATURE = float(os.getenv("CRITIC_TEMPERATURE", "0.1"))  # Critic agent (more precise)

    # Vertex AI location (only relevant when provider = google_vertexai)
    VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")


# =============================================================================
# LANGUAGE SETTINGS - Pengaturan Bahasa
# =============================================================================

class LanguageConfig:
    """System Language Configuration"""
    SUPPORTED_LANGUAGES = ("id", "en")
    SYSTEM_LANGUAGE = os.getenv("SYSTEM_LANGUAGE", "id")

    LANGUAGE_NAMES = {
        "id": "Indonesian",
        "en": "English",
    }

    @classmethod
    def set_language(cls, lang: str):
        if lang not in cls.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {lang}")
        cls.SYSTEM_LANGUAGE = lang

    @classmethod
    def get_display_name(cls) -> str:
        return cls.LANGUAGE_NAMES[cls.SYSTEM_LANGUAGE]

# =============================================================================
# STORY GENERATION SETTINGS - Pengaturan Pembuatan Cerita
# =============================================================================

class StoryConfig:
    """Konfigurasi untuk pembuatan cerita"""

    # Revision limits (Reflexion loop)
    MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "3"))  # Maksimum revisi (dibatasi 3 kali)

    # Quality thresholds
    QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", "4.0"))  # Minimum score to pass (1-5)
    COHERENCE_PENALTY_WEIGHT = float(os.getenv("COHERENCE_PENALTY_WEIGHT", "1.0"))  # Penalty per issue

    # Default values
    DEFAULT_LANGUAGE = "Indonesian" # Should dynamically use LanguageConfig.get_display_name() where used, or set logic locally.
    @classmethod
    def get_default_language(cls):
        return LanguageConfig.get_display_name()

    DEFAULT_STORY_LENGTH = os.getenv("DEFAULT_STORY_LENGTH", "")  # Empty default = flexible
    DEFAULT_TARGET_AGE = os.getenv("DEFAULT_TARGET_AGE", "")
    DEFAULT_STORY_STYLE = os.getenv("DEFAULT_STORY_STYLE", "")
    DEFAULT_EMOTIONAL_TONE = os.getenv("DEFAULT_EMOTIONAL_TONE", "mengangkat semangat")

    # Feature Flags for Writers (Default: Disabled)
    ENABLE_IMAGE_WRITER = os.getenv("ENABLE_IMAGE_WRITER", "false").lower() == "true"
    ENABLE_DIAGRAM_WRITER = os.getenv("ENABLE_DIAGRAM_WRITER", "false").lower() == "true"
    ENABLE_DIRECTOR = os.getenv("ENABLE_DIRECTOR", "false").lower() == "true"
    ENABLE_CRITIC_EVAL_METRICS = os.getenv("ENABLE_CRITIC_EVAL_METRICS", "false").lower() == "true"

    # Available story styles (Gaya cerita yang tersedia)
    STORY_STYLES = {
        "id": {
            "naratif": "Cerita naratif klasik dengan alur awal-tengah-akhir",
            "fabel": "Cerita dengan karakter hewan yang mengajarkan moral",
            "fantasi": "Cerita dengan elemen magis dan dunia imajinatif",
            "petualangan": "Cerita penuh aksi dan eksplorasi",
            "misteri": "Cerita dengan teka-teki yang harus dipecahkan",
            "studi_kasus": "Cerita berbasis kasus nyata/realistis untuk pembelajaran",
            "kisah_sehari_hari": "Cerita slice-of-life tentang kehidupan sehari-hari",
            "dongeng": "Cerita rakyat atau dongeng dengan pesan moral",
            "fiksi_ilmiah": "Cerita dengan elemen sains dan teknologi",
            "humor": "Cerita lucu dengan pesan tersembunyi"
        },
        "en": {
            "naratif": "Classic narrative story with beginning-middle-end plot",
            "fabel": "Story with animal characters teaching morals",
            "fantasi": "Story with magical elements and imaginative worlds",
            "petualangan": "Action-packed story and exploration",
            "misteri": "Story with puzzles to be solved",
            "studi_kasus": "Story based on real/realistic cases for learning",
            "kisah_sehari_hari": "Slice-of-life story about daily life",
            "dongeng": "Folktale or fairy tale with a moral message",
            "fiksi_ilmiah": "Story with science and technology elements",
            "humor": "Funny story with a hidden message"
        }
    }

    # Available narrative styles (Gaya narasi - monolog/dialog)
    NARRATIVE_STYLES = {
        "id": {
            "campuran": "Kombinasi narasi dan dialog (default, paling natural)",
            "dialog_dominan": "Lebih banyak dialog antar karakter, narasi minimal",
            "monolog_dominan": "Lebih banyak narasi/deskripsi, dialog minimal",
            "monolog_internal": "Fokus pada pikiran dan perasaan internal karakter",
            "dialog_murni": "Hampir seluruhnya dialog (seperti naskah drama)",
            "non_dialog": "TANPA dialog sama sekali - hanya narasi dan deskripsi kegiatan",
            "deskriptif": "Fokus pada deskripsi suasana, tempat, dan kegiatan tanpa percakapan"
        },
        "en": {
            "campuran": "Combination of narration and dialogue (default, most natural)",
            "dialog_dominan": "More dialogue between characters, minimal narration",
            "monolog_dominan": "More narration/description, minimal dialogue",
            "monolog_internal": "Focus on the character's internal thoughts and feelings",
            "dialog_murni": "Almost entirely dialogue (like a play script)",
            "non_dialog": "NO dialogue at all - only narration and activity descriptions",
            "deskriptif": "Focus on descriptions of atmosphere, places, and activities without conversation"
        }
    }

    # Available target age groups (Kelompok usia target)
    TARGET_AGE_GROUPS = {
        "id": {
            "5-7": "Anak usia dini (TK-SD kelas 1-2)",
            "8-10": "Anak usia SD (kelas 3-5)",
            "11-13": "Pra-remaja (kelas 6-SMP)",
            "14-17": "Remaja (SMA)",
            "18+": "Dewasa (mahasiswa dan umum)"
        },
        "en": {
            "5-7": "Early childhood (Kindergarten-1st/2nd grade)",
            "8-10": "Primary school children (3rd-5th grade)",
            "11-13": "Pre-teens (6th grade-Middle School)",
            "14-17": "Teens (High School)",
            "18+": "Adults (college students and general public)"
        }
    }

    # Available emotional tones (Nada emosional yang tersedia)
    EMOTIONAL_TONES = {
        "id": {
            "mengangkat_semangat": "Inspiratif dan memotivasi",
            "mengharukan": "Menyentuh hati dan emosional",
            "menegangkan": "Penuh ketegangan dan suspense",
            "lucu": "Menghibur dan ringan",
            "reflektif": "Mengajak berpikir dan introspeksi",
            "hangat": "Penuh kehangatan dan kasih sayang",
            "petualangan": "Penuh semangat dan keberanian"
        },
        "en": {
            "mengangkat_semangat": "Inspiring and motivating",
            "mengharukan": "Touching and emotional",
            "menegangkan": "Full of tension and suspense",
            "lucu": "Entertaining and light",
            "reflektif": "Thought-provoking and introspective",
            "hangat": "Full of warmth and affection",
            "petualangan": "Full of spirit and courage"
        }
    }


# =============================================================================

# =============================================================================


    # State tracking
    MAX_STATES_PER_EPISODE = int(os.getenv("MAX_STATES_PER_EPISODE", "50"))


# =============================================================================
# LIGHTRAG SETTINGS - Pengaturan LightRAG
# =============================================================================

class LightRAGConfig:
    """Konfigurasi untuk LightRAG (Knowledge Graph RAG)"""

    # LightRAG Server API
    API_URL = os.getenv("LIGHTRAG_API_URL")
    API_KEY = os.getenv("LIGHTRAG_API_KEY", "")  # Optional, if auth enabled

    # Query settings
    DEFAULT_MODE = os.getenv("LIGHTRAG_DEFAULT_MODE", "hybrid")  # local, global, hybrid, naive, mix
    TOP_K = int(os.getenv("LIGHTRAG_TOP_K", "5"))

    # Local storage (legacy)
    WORKING_DIR = os.getenv("LIGHTRAG_WORKING_DIR", "./data/lightrag_storage")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Ingestion filters
    SELECTIVE_INGESTION = os.getenv("LIGHTRAG_SELECTIVE_INGESTION", "true").lower() == "true"
    INGEST_MIN_LENGTH = int(os.getenv("LIGHTRAG_INGEST_MIN_LENGTH", "500")) # Min characters to ingest


# =============================================================================
# OBSERVABILITY SETTINGS - Pengaturan Observability
# =============================================================================

class ObservabilityConfig:
    """Konfigurasi untuk logging dan monitoring"""

    # Langfuse Configuration
    LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

    # Langfuse Project Info
    LANGFUSE_PROJECT_NAME = os.getenv("LANGFUSE_PROJECT_NAME", "skripsi")
    LANGFUSE_PROJECT_ID = os.getenv("LANGFUSE_PROJECT_ID", "cmiotu4on0006s007ssffnxlo")

    # Debug mode
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"






# =============================================================================
# PRINT CURRENT CONFIG - Cetak Konfigurasi Saat Ini
# =============================================================================

def print_config():
    """Print current configuration for debugging"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 KONFIGURASI SAAT INI")
    logger.info("=" * 60)

    logger.info("\n🤖 LLM Provider Configuration:")
    logger.info(f"   - Provider: {LLMProviderConfig.PROVIDER}")
    logger.info(f"   - Model: {LLMProviderConfig.default_model()}")
    logger.info(f"   - Parser Temperature: {ModelConfig.PARSER_TEMPERATURE}")
    logger.info(f"   - Researcher Temperature: {ModelConfig.RESEARCHER_TEMPERATURE}")
    logger.info(f"   - Planner Temperature: {ModelConfig.PLANNER_TEMPERATURE}")
    logger.info(f"   - Writer Temperature: {ModelConfig.WRITER_TEMPERATURE}")
    logger.info(f"   - Critic Temperature: {ModelConfig.CRITIC_TEMPERATURE}")

    logger.info("\n📖 Story Configuration:")
    logger.info(f"   - Max Revisions: {StoryConfig.MAX_REVISIONS}")
    logger.info(f"   - Quality Threshold: {StoryConfig.QUALITY_THRESHOLD}")
    logger.info(f"   - Default Language: {StoryConfig.DEFAULT_LANGUAGE}")
    logger.info(f"   - Default Story Length: {StoryConfig.DEFAULT_STORY_LENGTH}")



# =============================================================================
# RUN TEST - Jalankan Test Konfigurasi
# =============================================================================

if __name__ == "__main__":
    print_config()
