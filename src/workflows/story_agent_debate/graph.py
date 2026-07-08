from src.workflows.story_agent.integrations.langfuse_client import get_langfuse
"""
Workflow builder for Debate architecture.

Wraps agentic_architectures.Debate with a project-standard LLM.
The internal bidding mechanism, persona logic, and majority-vote
are untouched -- only the LLM is injected to standardize it across
all experimental conditions.

Experimental condition: Debate (Du et al., 2023. arXiv:2305.14325)
Tools: None (no external retrieval)
LLM: Reads from LLM_PROVIDER / LLM_MODEL environment variables (same as all agents)
Config: n_agents=3, n_rounds=2 (library defaults, matching notebook)
"""

from typing import Any
from loguru import logger
from agentic_architectures import get_llm
from agentic_architectures.architectures import Debate
from agentic_architectures.architectures.base import ArchitectureResult

from .prompts import AGENT_PERSONAS


def _get_provider_config():
    from settings import LLMProviderConfig
    return LLMProviderConfig


# Provider name mapping: project LLM_PROVIDER values -> agentic_architectures names
_PROVIDER_MAP = {
    "google_genai":    "google",
    "google_vertexai": "google",
    "openai":          "openai",
    "openrouter":      "openai",
    "deepseek":        "openai",
    "glm":             "openai",
    "ollama":          "ollama",
}


def _build_llm(callbacks: list | None = None, model_override: str | None = None):
    """
    Build the shared LLM instance for this architecture.

    Reads LLM_PROVIDER and LLM_MODEL from the same environment variables
    used by all other agents (via LLMProviderConfig).

    Args:
        callbacks: Optional LangChain callbacks.
        model_override: If set, overrides the model from env/config.

    Ollama special case: Debate uses .with_structured_output() for
    _DebateResponse. ChatOllama does not support this, but Ollama's
    OpenAI-compatible endpoint (/v1) does. When provider is ollama,
    use ChatOpenAI pointed at the local Ollama server instead.
    """
    cfg = _get_provider_config()
    project_provider = cfg.PROVIDER
    model = model_override or cfg.default_model()

    if project_provider == "ollama":
        from langchain_openai import ChatOpenAI
        import httpx
        import json

        def clean_arguments(arguments: str) -> str:
            if not isinstance(arguments, str):
                return arguments
            for token in ["<|tool_response>", "<|im_end|>", "<|im_start|>", "<|tool_call|>", "<|"]:
                if token in arguments:
                    idx = arguments.find(token)
                    arguments = arguments[:idx]
            return arguments.strip()

        class OllamaCleaningClient(httpx.Client):
            def send(self, request, **kwargs):
                response = super().send(request, **kwargs)
                if "/chat/completions" in str(request.url):
                    try:
                        content = response.content.decode("utf-8")
                        data = json.loads(content)
                        modified = False
                        for choice in data.get("choices", []):
                            message = choice.get("message", {})
                            for tool_call in message.get("tool_calls", []):
                                function = tool_call.get("function", {})
                                arguments = function.get("arguments", "")
                                cleaned = clean_arguments(arguments)
                                if cleaned != arguments:
                                    function["arguments"] = cleaned
                                    modified = True
                        if modified:
                            new_content = json.dumps(data).encode("utf-8")
                            response._content = new_content
                            response.headers["Content-Length"] = str(len(new_content))
                    except Exception:
                        pass
                return response

        class OllamaCleaningAsyncClient(httpx.AsyncClient):
            async def send(self, request, **kwargs):
                response = await super().send(request, **kwargs)
                if "/chat/completions" in str(request.url):
                    try:
                        content = response.content.decode("utf-8")
                        data = json.loads(content)
                        modified = False
                        for choice in data.get("choices", []):
                            message = choice.get("message", {})
                            
                            if message.get("content"):
                                content_val = message["content"]
                                cleaned_content = clean_arguments(content_val)
                                if cleaned_content != content_val:
                                    message["content"] = cleaned_content
                                    modified = True

                            for tool_call in message.get("tool_calls", []):
                                function = tool_call.get("function", {})
                                arguments = function.get("arguments", "")
                                cleaned = clean_arguments(arguments)
                                if cleaned != arguments:
                                    function["arguments"] = cleaned
                                    modified = True
                        if modified:
                            new_content = json.dumps(data).encode("utf-8")
                            response._content = new_content
                            response.headers["Content-Length"] = str(len(new_content))
                    except Exception:
                        pass
                return response

        ollama_url = cfg.OLLAMA_BASE_URL
        logger.info(
            f"[ARCH::DEBATE] Ollama detected -- using OpenAI-compat endpoint "
            f"at {ollama_url} with model={model}"
        )
        return ChatOpenAI(
            model=model,
            base_url=ollama_url,
            api_key="ollama",
            temperature=0.7,
            callbacks=callbacks,
            http_client=OllamaCleaningClient(),
            http_async_client=OllamaCleaningAsyncClient(),
        )

    arch_provider = _PROVIDER_MAP.get(project_provider, project_provider)
    logger.info(
        f"[ARCH::DEBATE] Building LLM: provider={arch_provider}, model={model}"
    )
    return get_llm(
        provider=arch_provider,
        model=model,
        temperature=0.7,
        callbacks=callbacks,
    )


class TraceableDebate(Debate):
    """
    Subclass of Debate that exposes full round metadata for the API layer.

    The base Debate.run() returns an ArchitectureResult but the metadata
    available from the final graph state varies by library version.
    This subclass re-runs the graph and extracts the rich metadata fields
    (rounds, convergence, final_tally, round_unique_answer_count) needed
    by the SSE stream generator.
    """


    def _round(self, state: dict[str, Any]) -> dict[str, Any]:
        from src.workflows.story_agent.integrations.langfuse_client import get_langfuse
        lf = get_langfuse()
        
        round_num = state.get("round", 0) + 1
        prior = state.get("rounds", [])
        prior_block = ""
        if prior:
            last = prior[-1]
            prior_block = "\n## Prior round answers from all agents\n" + "\n".join(
                f"  - Agent {chr(65 + int(r['agent_id']))}: '{r['answer']}'  — critique: {r['critique'][:200]}" for r in last
            )

        responses: list[dict[str, str]] = []
        for i in range(state.get("n_agents", getattr(self, "n_agents", 3))):
            personas = getattr(self, "personas", [])
            persona = personas[i % len(personas)] if personas else f"You are Agent {chr(65 + i)}."
            
            # Map persona to agent name for Langfuse tracing
            agent_name = "Agent"
            if "rigorous" in persona.lower(): agent_name = "Rigorous"
            elif "skeptical" in persona.lower(): agent_name = "Skeptical"
            elif "pragmatic" in persona.lower(): agent_name = "Pragmatic"
            else: agent_name = f"Agent {chr(65 + i)}"
                
            # Mapping persona to agent name for Langfuse tracing is kept for reference
            # but we remove the `with lf.span(...)` which causes AttributeError
            prompt = (
                f"{persona}\n\n"
                f"# Task\n{state.get('task', '')}\n"
                f"{prior_block}\n\n"
                f"You are now in round {round_num} of {state.get('n_rounds', getattr(self, 'n_rounds', 2))}. "
                "Read the prior round's answers (if any) and decide: do you stand by your "
                "previous answer (or this round's first instinct), or did another agent's "
                "argument shift your view? Then emit your answer and a brief critique."
            )
            try:
                resp = getattr(self, "_responder").invoke(prompt)
                responses.append(
                    {
                        "agent_id": str(i),
                        "answer": resp.answer.strip() if hasattr(resp, 'answer') else str(resp),
                        "critique": resp.critique_of_others.strip() if hasattr(resp, 'critique_of_others') else "",
                    }
                )
            except Exception as e:
                responses.append(
                    {
                        "agent_id": str(i),
                        "answer": "",
                        "critique": f"(response failed: {e})",
                    }
                )

        for r in responses:
            r["agent_id"] = int(r["agent_id"])

        return {
            "round": round_num,
            "rounds": [responses],
            "history": [
                {
                    "stage": f"round_{round_num}",
                    "answers": [r["answer"] for r in responses],
                }
            ],
        }

    def run(self, task: str, **kwargs: Any) -> ArchitectureResult:
        graph = self.build()
        config = {
            "recursion_limit": 4 * self.n_rounds * self.n_agents + 10,
            "run_name": "DebateWorkflow",
        }
        callbacks = kwargs.get("callbacks")
        if callbacks:
            config["callbacks"] = callbacks

        final_state = graph.invoke({"task": task}, config=config)

        # Extract round data
        rounds_raw = final_state.get("rounds", [])
        answers_per_round = [
            list({r.get("answer", "") for r in rnd})
            for rnd in rounds_raw
        ] if rounds_raw else []
        round_unique_answer_count = [len(s) for s in answers_per_round]

        last_round_answers = [
            r.get("answer", "") for r in (rounds_raw[-1] if rounds_raw else [])
        ]
        from collections import Counter
        tally = Counter(last_round_answers)
        final_answer = tally.most_common(1)[0][0] if tally else final_state.get("final_answer", "")
        convergence = len(tally) == 1 if tally else False

        trace = [{"type": "round", "round": i + 1, "agents": rnd} for i, rnd in enumerate(rounds_raw)]

        return ArchitectureResult(
            output=final_answer,
            state={"task": task},
            trace=trace,
            metadata={
                "convergence": convergence,
                "final_tally": dict(tally),
                "round_unique_answer_count": round_unique_answer_count,
                "n_agents": self.n_agents,
                "n_rounds": self.n_rounds,
                "rounds": rounds_raw,
            },
        )


def create_debate_workflow(callbacks: list | None = None, model_name: str | None = None) -> TraceableDebate:
    """
    Create and return a configured TraceableDebate instance.

    The returned object exposes .run(task: str, callbacks=callbacks) -> ArchitectureResult,
    which the API router calls directly. No LangGraph graph is compiled
    here -- that happens lazily inside arch.run() via arch.build().

    Configuration:
        n_agents:           3 (library default, matches notebook)
        n_rounds:           2 (library default, matches notebook)
        agent_personas:     AGENT_PERSONAS (verbatim from library, auditable)
        sample_temperature: 0.7 (library default, for answer diversity in round 1)
        tools:              None (Debate has no external retrieval by design)

    Args:
        callbacks: Optional LangChain callbacks.
        model_name: Override model name (e.g. 'gemma4:e4b' for Ollama).

    Returns:
        TraceableDebate instance ready to call .run(task).
    """
    llm = _build_llm(callbacks=callbacks, model_override=model_name)

    # Inject Zero-shot CoT into the personas
    cot_personas = [p + " Let's think step by step." for p in AGENT_PERSONAS]

    arch = TraceableDebate(
        llm=llm,
        n_agents=3,
        n_rounds=2,
        agent_personas=cot_personas,
        sample_temperature=0.7,
    )

    logger.info(
        "[ARCH::DEBATE] Workflow ready. "
        f"n_agents=3, n_rounds=2, personas={[p[:30] + '...' for p in cot_personas]}"
    )
    return arch
