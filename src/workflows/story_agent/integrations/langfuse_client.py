"""
Langfuse Client - Backward-Compatible Shim.

This module re-exports all public symbols from the ``langfuse`` sub-package
so that every existing import path continues to work without modification:

    from .integrations.langfuse_client import get_langfuse
    from ..integrations.langfuse_client import LangfuseClient
    from workflows.story_agent.integrations.langfuse_client import LangfuseGraphCallbackHandler

The actual implementation lives in ``integrations/langfuse/``.
"""

from .langfuse import (  # noqa: F401
    LangfuseClient,
    get_langfuse,
    TraceWrapper,
    SpanWrapper,
    LangfuseGraphCallbackHandler,
)

__all__ = [
    "LangfuseClient",
    "get_langfuse",
    "TraceWrapper",
    "SpanWrapper",
    "LangfuseGraphCallbackHandler",
]
