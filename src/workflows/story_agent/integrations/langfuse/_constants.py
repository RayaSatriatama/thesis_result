"""
Langfuse Integration Constants and Conditional Imports.

Centralizes all feature-flag constants and conditional dependency imports
so other modules in this package can reference them without duplicating
try/except blocks.
"""

from typing import Optional

# Import Langfuse
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore[assignment,misc]

# Import OpenTelemetry for VertexAI token tracking
OTEL_AVAILABLE = False
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry import trace
    OTEL_AVAILABLE = True
except ImportError:
    TracerProvider = None  # type: ignore[assignment,misc]
    OTLPSpanExporter = None  # type: ignore[assignment,misc]
    SimpleSpanProcessor = None  # type: ignore[assignment,misc]
    trace = None  # type: ignore[assignment]

# Import VertexAI Instrumentor
VERTEX_INSTRUMENTOR_AVAILABLE = False
try:
    from openinference.instrumentation.vertexai import VertexAIInstrumentor
    VERTEX_INSTRUMENTOR_AVAILABLE = True
except ImportError:
    VertexAIInstrumentor = None  # type: ignore[assignment,misc]

# Import OpenAI Instrumentor (for DeepSeek, GLM, Ollama, OpenAI)
OPENAI_INSTRUMENTOR_AVAILABLE = False
try:
    from openinference.instrumentation.openai import OpenAIInstrumentor
    OPENAI_INSTRUMENTOR_AVAILABLE = True
except ImportError:
    OpenAIInstrumentor = None  # type: ignore[assignment,misc]
