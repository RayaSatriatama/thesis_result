"""
Workflow builder for Blackboard architecture (C4).

Wraps agentic_architectures.Blackboard with the default knowledge sources
and a project-standard LLM. The internal bidding mechanism, confidence
scoring, and synthesis logic are untouched -- only the LLM is injected
to standardize it across all experimental conditions.

Experimental condition: C4 - Blackboard
Tools: None (no external retrieval)
Knowledge sources: DEFAULT_KNOWLEDGE_SOURCES (verbatim library defaults)
LLM: Reads from LLM_PROVIDER / LLM_MODEL environment variables (same as all agents)
"""

from typing import Any
import os
from loguru import logger
from agentic_architectures import get_llm
from agentic_architectures.architectures import Blackboard
from agentic_architectures.architectures.base import ArchitectureResult

from .prompts import DEFAULT_KNOWLEDGE_SOURCES

# Lazy import to avoid circular dependency at module load time
def _get_provider_config():
    from settings import LLMProviderConfig
    return LLMProviderConfig


# Provider name mapping: project's LLM_PROVIDER values -> agentic_architectures provider names
_PROVIDER_MAP = {
    "google_genai":   "google",
    "google_vertexai": "google",
    "openai":         "openai",
    "openrouter":     "openai",   # openrouter uses openai-compatible interface
    "deepseek":       "openai",   # deepseek uses openai-compatible interface
    "glm":            "openai",
    "ollama":         "ollama",
}


def _build_llm(callbacks: list | None = None):
    """
    Build the shared LLM instance for this architecture.

    Reads LLM_PROVIDER and LLM_MODEL from the same environment variables
    used by all other agents in the project (via LLMProviderConfig).
    Maps provider names to the identifiers expected by agentic_architectures.

    Ollama special case: Blackboard requires .with_structured_output() for the
    bidding mechanism (_AgentBid Pydantic model). ChatOllama does not support
    this, but Ollama's OpenAI-compatible endpoint (/v1) does. When the provider
    is ollama, we use ChatOpenAI pointed at the local Ollama server instead.
    """
    cfg = _get_provider_config()
    project_provider = cfg.PROVIDER
    model = cfg.default_model()

    if project_provider == "ollama":
        from langchain_openai import ChatOpenAI
        ollama_url = cfg.OLLAMA_BASE_URL  # e.g. http://localhost:11434/v1
        logger.info(
            f"[ARCH::BLACKBOARD] Ollama detected -- using OpenAI-compat endpoint "
            f"at {ollama_url} with model={model}"
        )
        return ChatOpenAI(
            model=model,
            base_url=ollama_url,
            api_key="ollama",  # required field, value is ignored by Ollama
            temperature=0.7,
            callbacks=callbacks,
        )

    arch_provider = _PROVIDER_MAP.get(project_provider, project_provider)
    logger.info(
        f"[ARCH::BLACKBOARD] Building LLM: provider={arch_provider}, model={model}"
    )
    return get_llm(
        provider=arch_provider,
        model=model,
        temperature=0.7,
        callbacks=callbacks,
    )


class TraceableBlackboard(Blackboard):
    """
    Subclass of Blackboard that supports passing callbacks to the CompiledStateGraph invoke call.
    This allows Langfuse langchain CallbackHandler to trace the entire graph execution.
    """
    def run(self, task: str, **kwargs: Any) -> ArchitectureResult:
        from agentic_architectures.architectures.base import ArchitectureResult
        from agentic_architectures.architectures.blackboard import _count_invocations

        callbacks = kwargs.get("callbacks", None)
        graph = self.build()
        config = {
            "recursion_limit": 4 * self.max_rounds + 10,
            "run_name": "BlackboardWorkflow",
        }
        if callbacks:
            config["callbacks"] = callbacks

        final_state = graph.invoke(
            {"task": task, "round": 0, "max_rounds": self.max_rounds},
            config=config,
        )

        contributions = final_state.get("blackboard", [])
        trace = [{"type": "contribution", **c} for c in contributions]
        return ArchitectureResult(
            output=final_state.get("final_synthesis", ""),
            state={
                "task": task,
                "agent_invocation_counts": _count_invocations(contributions),
            },
            trace=trace,
            metadata={
                "total_rounds": final_state.get("round", 0),
                "agents_available": len(self.knowledge_sources),
                "agents_who_contributed": len({c["agent"] for c in contributions}),
                "max_rounds": self.max_rounds,
            },
        )


def create_blackboard_workflow(callbacks: list | None = None) -> TraceableBlackboard:
    """
    Create and return a configured TraceableBlackboard instance.

    The returned object exposes .run(task: str, callbacks=callbacks) -> ArchitectureResult,
    which the API router calls directly. No LangGraph graph is compiled
    here -- that happens lazily inside arch.run() via arch.build().

    Configuration:
        knowledge_sources: DEFAULT_KNOWLEDGE_SOURCES (4 roles: optimist,
                           skeptic, historian, quantitative)
        max_rounds:        5  (reduced from library default of 6 for
                           cost parity across conditions)
        min_confidence:    3  (library default)
        tools:             None (blackboard has no external tool support
                           by design)

    Returns:
        TraceableBlackboard instance ready to call .run(task).
    """
    llm = _build_llm(callbacks=callbacks)

    arch = TraceableBlackboard(
        llm=llm,
        knowledge_sources=DEFAULT_KNOWLEDGE_SOURCES,
        max_rounds=5,
        min_confidence=3,
    )

    logger.info(
        "[ARCH::BLACKBOARD] Workflow ready. "
        f"Roles: {list(DEFAULT_KNOWLEDGE_SOURCES.keys())}, "
        "max_rounds=5, min_confidence=3"
    )
    return arch
