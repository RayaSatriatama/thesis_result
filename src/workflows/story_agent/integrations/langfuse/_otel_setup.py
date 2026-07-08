"""
OpenTelemetry Instrumentation Setup for Langfuse.

Extracted from LangfuseClient._setup_otel_instrumentation.
Handles OTLP exporter configuration, tracer provider, and
provider-specific instrumentor registration.

Docs: https://langfuse.com/docs/integrations/google-vertex-ai
"""

import base64

from loguru import logger

from settings import ObservabilityConfig

from ._constants import (
    OTEL_AVAILABLE,
    OPENAI_INSTRUMENTOR_AVAILABLE,
    VERTEX_INSTRUMENTOR_AVAILABLE,
    OTLPSpanExporter,
    SimpleSpanProcessor,
    TracerProvider,
    trace,
)


def setup_otel_instrumentation() -> bool:
    """
    Setup OpenTelemetry untuk automatic token tracking (provider-agnostic).

    Mengirim trace langsung ke Langfuse OTLP endpoint.
    Provider yang didukung:
      - google_vertexai : openinference-instrumentation-vertexai
      - openai-compatible (deepseek, glm, ollama, openai):
          openinference-instrumentation-openai

    Docs: https://langfuse.com/docs/integrations/google-vertex-ai

    Returns:
        True if OTel was initialized successfully, False otherwise.
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not installed. Run: pip install opentelemetry-sdk opentelemetry-exporter-otlp")
        return False

    if not VERTEX_INSTRUMENTOR_AVAILABLE:
        logger.warning("VertexAI Instrumentor not installed. Run: pip install openinference-instrumentation-vertexai")
        return False

    # Validate keys before attempting connection to prevent 401 errors
    pk = (ObservabilityConfig.LANGFUSE_PUBLIC_KEY or "").strip()
    sk = (ObservabilityConfig.LANGFUSE_SECRET_KEY or "").strip()

    if not pk or not sk or pk.startswith("pk-lf-placeholder") or sk.startswith("sk-lf-placeholder"):
        logger.debug("Langfuse keys missing or invalid - skipping OTLP token tracking to prevent connection errors")
        return False

    try:
        # Configure OTLP exporter to send to Langfuse
        # Langfuse OTLP endpoint: https://cloud.langfuse.com/api/public/otel/v1/traces (or self-hosted)
        langfuse_host = ObservabilityConfig.LANGFUSE_HOST.rstrip('/')
        otlp_endpoint = f"{langfuse_host}/api/public/otel/v1/traces"

        # Create Basic Auth header for Langfuse
        auth_string = f"{ObservabilityConfig.LANGFUSE_PUBLIC_KEY}:{ObservabilityConfig.LANGFUSE_SECRET_KEY}"
        auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        # Setup OTLP exporter with Langfuse auth
        exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            headers={"Authorization": f"Basic {auth_bytes}"}
        )

        # Create and set tracer provider (only if not already set)
        existing_provider = trace.get_tracer_provider()
        # Check if a real provider is already set (not the default NoOpTracerProvider)
        provider_name = type(existing_provider).__name__
        if provider_name == "ProxyTracerProvider" or "NoOp" in provider_name:
            provider = TracerProvider()
            provider.add_span_processor(SimpleSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
        else:
            # Provider already exists, just add our exporter
            existing_provider.add_span_processor(SimpleSpanProcessor(exporter))

        # NOTE: VertexAI Instrumentor is DISABLED due to event loop conflicts
        # The instrumentor wraps gRPC calls which causes "Event loop is closed" errors
        # when used with async frameworks. Token tracking is handled manually instead.
        # VertexAIInstrumentor().instrument()

        # Optionally instrument OpenAI-compatible calls (DeepSeek, GLM, Ollama, OpenAI)
        try:
            from settings import LLMProviderConfig  # noqa: PLC0415
            _provider = LLMProviderConfig.PROVIDER
        except Exception:
            _provider = "google_vertexai"

        _openai_like = _provider in ("openai", "deepseek", "glm", "ollama")
        if _openai_like and OPENAI_INSTRUMENTOR_AVAILABLE:
            # Disabled OpenAIInstrumentor to avoid duplicate ChatCompletion spans.
            # All generations are logged manually via log_generation() with custom names.
            logger.info(
                f"[LANGFUSE::INISIALISASI] OpenAI Instrumentor dinonaktifkan untuk "
                f"mencegah duplikasi ChatCompletion pada provider '{_provider}'"
            )
        elif _openai_like and not OPENAI_INSTRUMENTOR_AVAILABLE:
            logger.info(
                "[LANGFUSE::INFO] openinference-instrumentation-openai tidak tersedia. "
                "Token otomatis tidak dilacak. "
                "Instal: pip install openinference-instrumentation-openai"
            )

        logger.success("[LANGFUSE::INISIALISASI] OpenTelemetry initialized (provider-agnostic)")
        return True

    except Exception as e:
        logger.warning(f"[LANGFUSE::GALAT] OpenTelemetry setup failed: {e}")
        return False
