"""
LLM Factory - Abstraksi Provider untuk Semua Agent

Mendukung berbagai provider LLM melalui satu titik konfigurasi:
  - Google Vertex AI  (LLM_PROVIDER=google_vertexai)  [default]
  - Google GenAI API  (LLM_PROVIDER=google_genai)
  - OpenAI            (LLM_PROVIDER=openai)
  - DeepSeek          (LLM_PROVIDER=deepseek)
  - GLM / Zhipu AI    (LLM_PROVIDER=glm)
  - Ollama            (LLM_PROVIDER=ollama)

Konfigurasi melalui .env:
  LLM_PROVIDER      = deepseek
  LLM_MODEL         = deepseek-chat
  DEEPSEEK_API_KEY  = sk-...

  LLM_PROVIDER      = glm
  LLM_MODEL         = glm-4-flash
  GLM_API_KEY       = ...

  LLM_PROVIDER      = google_genai
  LLM_MODEL         = gemini-2.5-flash
  GEMINI_API_KEY    = AIza...

  LLM_PROVIDER      = google_vertexai   (butuh credential.json)
  LLM_MODEL         = gemini-2.5-flash
  GOOGLE_CLOUD_PROJECT = my-project

Semua provider mengembalikan BaseChatModel dari LangChain sehingga
interoperabel dengan .with_structured_output(), callbacks, dsb.

Langfuse:
  Tracing manual (start_span / end_span) bekerja sama untuk semua provider.
  Auto-instrumentasi token OTel tersedia untuk Google Vertex dan OpenAI.
  Lihat: integrations/langfuse_client.py
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Mapping, Optional

from loguru import logger

# LangChain tipe dasar (selalu tersedia)
from langchain_core.language_models.chat_models import BaseChatModel


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_google_credentials():
    """
    Muat Google service-account credentials dari credential.json.
    Hanya dipanggil ketika provider = google_vertexai.
    """
    import json
    from google.oauth2 import service_account

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cred_path = os.path.join(project_root, "credential.json")
    if not os.path.exists(cred_path):
        raise FileNotFoundError(
            f"credential.json tidak ditemukan di {cred_path}. "
            "Gunakan LLM_PROVIDER lain atau letakkan file credential."
        )
    creds = service_account.Credentials.from_service_account_file(cred_path)
    with open(cred_path) as f:
        meta = json.load(f)
    project_id = meta.get("project_id", "")
    return creds, project_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_llm(
    temperature: Optional[float] = None,
    model_name: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    openrouter_provider_preferences: Optional[Mapping[str, Any]] = None,
) -> BaseChatModel:
    """
    Buat instance LLM berdasarkan LLM_PROVIDER (atau argumen `provider`).

    Args:
        temperature : Suhu sampling (0.0 = deterministik, 1.0 = kreatif).
        model_name  : Nama model yang dipakai; jika None pakai default provider.
        provider    : Override provider sementara (jarang dipakai langsung).
        openrouter_provider_preferences: Objek ``provider`` OpenRouter yang
            dikirim apa adanya pada request. Hanya valid untuk OpenRouter,
            misalnya ``{"require_parameters": True}``.

    Returns:
        BaseChatModel yang kompatibel dengan LangChain.

    Raises:
        ValueError  : Jika provider tidak dikenal atau konfigurasi tidak lengkap.
        ImportError : Jika paket untuk provider belum diinstal.
    """
    # Import settings lazily agar tidak ada circular import
    from settings import LLMProviderConfig  # noqa: PLC0415

    _provider = provider or LLMProviderConfig.PROVIDER
    _model = model_name or LLMProviderConfig.default_model()

    logger.debug(f"[LLM_FACTORY] provider={_provider}, model={_model}, temp={temperature}")

    # ------------------------------------------------------------------
    # Google Vertex AI
    # ------------------------------------------------------------------
    if _provider == "google_vertexai":
        try:
            from langchain_google_vertexai import ChatVertexAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-google-vertexai tidak terinstal. "
                "Jalankan: pip install langchain-google-vertexai"
            ) from exc

        creds, project_id = _load_google_credentials()
        project_id = LLMProviderConfig.GOOGLE_PROJECT or project_id
        location   = LLMProviderConfig.GOOGLE_LOCATION

        kwargs: dict = dict(
            model_name=_model,
            credentials=creds,
            project=project_id,
            location=location,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature

        return ChatVertexAI(**kwargs)

    # ------------------------------------------------------------------
    # Google Generative AI (GenAI API key)
    # ------------------------------------------------------------------
    elif _provider == "google_genai":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-google-genai tidak terinstal. "
                "Jalankan: pip install langchain-google-genai"
            ) from exc

        api_key = (
            LLMProviderConfig.GOOGLE_API_KEY
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY atau GOOGLE_API_KEY harus diset "
                "saat menggunakan LLM_PROVIDER=google_genai"
            )

        kwargs: dict = dict(
            model=_model,
            google_api_key=api_key,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature

        return ChatGoogleGenerativeAI(**kwargs)

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    elif _provider == "openai":
        try:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-openai tidak terinstal. "
                "Jalankan: pip install langchain-openai"
            ) from exc

        api_key = (
            LLMProviderConfig.API_KEY
            or LLMProviderConfig.OPENAI_API_KEY
            or os.getenv("OPENAI_API_KEY", "")
        )
        kwargs: dict = dict(model=_model, api_key=api_key)
        if temperature is not None:
            kwargs["temperature"] = temperature
        if LLMProviderConfig.CUSTOM_BASE_URL:
            kwargs["base_url"] = LLMProviderConfig.CUSTOM_BASE_URL
        return ChatOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # OpenRouter  (OpenAI-compatible, 200+ models)
    # ------------------------------------------------------------------
    elif _provider == "openrouter":
        try:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-openai tidak terinstal. "
                "Jalankan: pip install langchain-openai"
            ) from exc

        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("LLM_API_KEY")
            or LLMProviderConfig.OPENROUTER_API_KEY
            or LLMProviderConfig.API_KEY
        )
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY harus diset saat menggunakan LLM_PROVIDER=openrouter"
            )

        base_url = (
            os.getenv("OPENROUTER_BASE_URL")
            or LLMProviderConfig.OPENROUTER_BASE_URL
        )

        # OpenRouter mendukung header opsional untuk pelacakan ranking
        default_headers: dict = {}
        site_url = os.getenv("OPENROUTER_SITE_URL") or LLMProviderConfig.OPENROUTER_SITE_URL
        app_name = os.getenv("OPENROUTER_APP_NAME") or LLMProviderConfig.OPENROUTER_APP_NAME
        if site_url:
            default_headers["HTTP-Referer"] = site_url
        if app_name:
            default_headers["X-Title"] = app_name

        kwargs: dict = dict(
            model=_model or "openai/gpt-4o-mini",
            api_key=api_key,
            base_url=base_url,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        if default_headers:
            kwargs["default_headers"] = default_headers
        if openrouter_provider_preferences is None:
            raw_preferences = os.getenv("OPENROUTER_PROVIDER_PREFERENCES", "").strip()
            if raw_preferences:
                try:
                    openrouter_provider_preferences = json.loads(raw_preferences)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "OPENROUTER_PROVIDER_PREFERENCES must be a JSON object"
                    ) from exc
                if not isinstance(openrouter_provider_preferences, dict):
                    raise ValueError("OPENROUTER_PROVIDER_PREFERENCES must be a JSON object")
        if openrouter_provider_preferences:
            kwargs["extra_body"] = {
                "provider": dict(openrouter_provider_preferences),
            }

        return ChatOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # DeepSeek  (OpenAI-compatible endpoint)
    # ------------------------------------------------------------------
    elif _provider == "deepseek":
        try:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-openai tidak terinstal. "
                "Jalankan: pip install langchain-openai"
            ) from exc

        api_key = (
            os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("LLM_API_KEY")
            or LLMProviderConfig.DEEPSEEK_API_KEY
            or LLMProviderConfig.API_KEY
        )
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY harus diset saat menggunakan LLM_PROVIDER=deepseek"
            )

        kwargs: dict = dict(
            model=_model or "deepseek-chat",
            api_key=api_key,
            base_url=LLMProviderConfig.DEEPSEEK_BASE_URL,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature

        return ChatOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # GLM / Zhipu AI  (OpenAI-compatible endpoint)
    # ------------------------------------------------------------------
    elif _provider == "glm":
        try:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-openai tidak terinstal. "
                "Jalankan: pip install langchain-openai"
            ) from exc

        api_key = (
            os.getenv("GLM_API_KEY")
            or os.getenv("ZHIPUAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or LLMProviderConfig.GLM_API_KEY
            or LLMProviderConfig.API_KEY
        )
        if not api_key:
            raise ValueError(
                "GLM_API_KEY atau ZHIPUAI_API_KEY harus diset "
                "saat menggunakan LLM_PROVIDER=glm"
            )

        kwargs: dict = dict(
            model=_model or "glm-4-flash",
            api_key=api_key,
            base_url=LLMProviderConfig.GLM_BASE_URL,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature

        return ChatOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # Ollama  (local, OpenAI-compatible)
    # ------------------------------------------------------------------
    elif _provider == "ollama":
        try:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "langchain-openai tidak terinstal. "
                "Jalankan: pip install langchain-openai"
            ) from exc

        kwargs: dict = dict(
            model=_model or "llama3.2",
            api_key="ollama",
            base_url=LLMProviderConfig.OLLAMA_BASE_URL,
        )
        if temperature is not None:
            kwargs["temperature"] = temperature

        return ChatOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # Unknown provider
    # ------------------------------------------------------------------
    else:
        raise ValueError(
            f"LLM provider tidak dikenal: '{_provider}'. "
            "Pilihan valid: google_vertexai, google_genai, openai, deepseek, glm, ollama"
        )


def get_llm_for_agent(
    agent_name: str,
    *,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
) -> BaseChatModel:
    """
    Buat LLM dengan suhu yang sesuai untuk setiap jenis agent.

    Agent  | Suhu default | Catatan
    -------|--------------|-------------------------------------
    parser      | 0.3  | Parsing input pengguna
    researcher  | 0.5  | Riset konten
    planner     | 0.7  | Perancangan alur cerita
    writer      | 0.9  | Penulisan cerita (lebih kreatif)
    critic      | 0.1  | Evaluasi (lebih presisi)
    supervisor  | 0.3  | Routing (deterministik)
    diagram     | 0.5  | Diagram edukasi
    default     | 0.7  | Fallback

    Args:
        agent_name : Nama agent (lihat tabel di atas).
        model_name : Override nama model jika perlu.
        provider   : Override provider jika perlu.

    Returns:
        BaseChatModel yang dikonfigurasi untuk agent tersebut.
    """
    from settings import ModelConfig  # noqa: PLC0415

    temperature_map = {
        "parser":     ModelConfig.PARSER_TEMPERATURE,
        "researcher": ModelConfig.RESEARCHER_TEMPERATURE,
        "planner":    ModelConfig.PLANNER_TEMPERATURE,
        "writer":     ModelConfig.WRITER_TEMPERATURE,
        "critic":     ModelConfig.CRITIC_TEMPERATURE,
        "supervisor": ModelConfig.PARSER_TEMPERATURE,   # deterministic routing
        "diagram":    0.5,
        "director":   0.7,   # creative but structured output
    }
    temperature = temperature_map.get(agent_name.lower(), 0.7)

    return get_llm(temperature=temperature, model_name=model_name, provider=provider)
