"""
Workflow builder for STORM architecture.

Wraps agentic_architectures.STORM with a project-standard LLM and
optional Tavily web search. The internal pipeline stages (perspectives,
questions, answers, outline, write) are untouched -- only the LLM
and search function are injected.

Experimental condition: STORM (Shao et al., 2024. arXiv:2402.14207)
Tools: web_search_fn via Tavily (optional -- graceful degradation if unavailable)
LLM: Reads from LLM_PROVIDER / LLM_MODEL environment variables (same as all agents)
Config: n_perspectives=3, questions_per_perspective=2 (matching notebook)
"""

from typing import Any, Callable
from loguru import logger
from agentic_architectures import get_llm
from agentic_architectures.architectures import STORM
from agentic_architectures.architectures.base import ArchitectureResult
from agentic_architectures.architectures.storm import STORMState

from .prompts import DEFAULT_N_PERSPECTIVES, DEFAULT_QUESTIONS_PER_PERSPECTIVE
import asyncio

ENABLE_LIGHTRAG = True
ENABLE_WEBSEARCH = True


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

    Ollama special case: STORM uses .with_structured_output() for
    structured list outputs. ChatOllama does not support this reliably,
    so fall back to ChatOpenAI with the Ollama OpenAI-compatible endpoint.
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
            f"[ARCH::STORM] Ollama detected -- using OpenAI-compat endpoint "
            f"at {ollama_url} with model={model}"
        )
        return ChatOpenAI(
            model=model,
            base_url=ollama_url,
            api_key="ollama",
            temperature=1.0,
            callbacks=callbacks,
            http_client=OllamaCleaningClient(),
            http_async_client=OllamaCleaningAsyncClient(),
        )

    arch_provider = _PROVIDER_MAP.get(project_provider, project_provider)
    logger.info(
        f"[ARCH::STORM] Building LLM: provider={arch_provider}, model={model}"
    )
    return get_llm(
        provider=arch_provider,
        model=model,
        temperature=1.0,
        callbacks=callbacks,
    )


def _build_web_search_fn(language: str = "id", model_name: str | None = None) -> Callable[[str], list[str]] | None:
    """
    Build the web search function for STORM's answer stage using ResearchAgent.
    """
    if not ENABLE_LIGHTRAG and not ENABLE_WEBSEARCH:
        logger.info("[ARCH::STORM] Both LightRAG and WebSearch are disabled via hardcode.")
        return None

    try:
        from src.workflows.story_agent.agents.researcher import ResearchAgent
        
        def web_search_fn(query: str) -> list[str]:
            # Run the async operations in a new event loop since we are in a thread
            # without a running event loop (due to asyncio.to_thread).
            async def _do_search():
                researcher = ResearchAgent(model_name=model_name)
                # Initialize LightRAG if enabled
                if ENABLE_LIGHTRAG:
                    try:
                        from src.workflows.story_agent.integrations.lightrag_client import get_lightrag_client
                        researcher.lightrag = get_lightrag_client(language)
                    except Exception as e:
                        logger.warning(f"[ARCH::STORM] Failed to initialize LightRAG: {e}")
                
                results = []
                
                # Fetch from Web Search
                if ENABLE_WEBSEARCH:
                    try:
                        web_text, web_sources = await researcher._search_web(query, language=language, theme=query)
                        
                        # Source Filtering: Exclude unreliable domains based on Wikipedia Reliable Sources
                        unreliable_domains = ["reddit.com", "quora.com", "yahoo.com", "twitter.com", "facebook.com", "instagram.com", "tiktok.com"]
                        filtered_sources = []
                        for src in web_sources:
                            uri = src.get("uri", "").lower()
                            if not any(domain in uri for domain in unreliable_domains):
                                filtered_sources.append(src)
                        
                        if web_text:
                            # Attach source URLs as citations
                            source_str = "\n".join([f"[{i+1}] {s.get('uri')}" for i, s in enumerate(filtered_sources)])
                            if source_str:
                                results.append(f"Web Search Context:\n{web_text}\n\nSources:\n{source_str}")
                            else:
                                results.append(f"Web Search Context:\n{web_text}")
                    except Exception as e:
                        logger.warning(f"[ARCH::STORM] Web search failed: {e}")
                
                # Fetch from LightRAG
                if ENABLE_LIGHTRAG and researcher.lightrag:
                    try:
                        kg_text = await researcher._query_kg(query)
                        if kg_text:
                            results.append(f"LightRAG Context:\n{kg_text}")
                    except Exception as e:
                        logger.warning(f"[ARCH::STORM] LightRAG query failed: {e}")
                
                return results

            return asyncio.run(_do_search())

        logger.info(f"[ARCH::STORM] Research integrations enabled. LightRAG: {ENABLE_LIGHTRAG}, WebSearch: {ENABLE_WEBSEARCH}")
        return web_search_fn

    except Exception as exc:
        logger.warning(
            f"[ARCH::STORM] Could not initialize Research integrations: {exc}. "
            "STORM will run without external retrieval."
        )
        return None


class TraceableSTORM(STORM):
    """
    Subclass of STORM that supports passing callbacks to the graph invoke call
    and surfaces full pipeline metadata for the API layer.

    STORM.run() already returns rich metadata (perspectives, questions, outline,
    article_chars) -- this subclass preserves that and adds callback injection.
    """

    def _gen_questions(self, state: STORMState) -> dict[str, Any]:
        all_q: list[dict[str, Any]] = []
        all_a: list[dict[str, str]] = []
        
        for persp in state.get("perspectives", []):
            history_str = ""
            conversation_history = []
            
            for turn in range(self.questions_per_perspective):
                try:
                    # Prompt LLM to ask next specific follow-up question
                    prompt = (
                        f"# Topic\n{state.get('topic', '')}\n\n"
                        f"# Perspective\n{persp}\n\n"
                        f"# Conversation History\n{history_str}\n\n"
                        f"Generate 1 specific follow-up research question from this perspective. "
                        f"It MUST be different from previous questions and explore new details."
                    )
                    q_obj = self._questions.invoke(prompt)
                    
                    if not q_obj.questions:
                        continue
                    
                    q_text = q_obj.questions[0].strip()
                    if not q_text:
                        continue
                    
                    # 2. Get Answer
                    if self.web_search_fn:
                        web = self.web_search_fn(q_text)
                        ctx = "\n\n".join(web) if web else "(no web results)"
                        ans = str(
                            self.llm.invoke(
                                f"Answer comprehensively using the provided contexts. "
                                f"IMPORTANT: You MUST preserve and include the source URLs or Citations from the contexts in your answer.\n\n"
                                f"# Contexts\n{ctx}\n\n# Q: {q_text}\nA:"
                            ).content
                        ).strip()
                    else:
                        ans = str(
                            self.llm.invoke(f"Answer comprehensively from your knowledge.\n\n# Q: {q_text}\nA:").content
                        ).strip()
                    
                    # Update state variables
                    all_q.append({"perspective": persp, "question": q_text})
                    all_a.append({"question": q_text, "answer": ans})
                    
                    # Update local conversation history for the next turn
                    conversation_history.append(f"Q: {q_text}\nA: {ans}")
                    history_str = "\n\n".join(conversation_history)
                except Exception as e:
                    logger.warning(f"[ARCH::STORM] Conversational Q&A failed for perspective '{persp}', turn {turn}: {e}")
                    continue
        
        return {
            "questions": all_q,
            "answers": all_a,
            "history": [{"stage": "questions", "n_total": len(all_q)}],
        }

    def _answer_questions(self, state: STORMState) -> dict[str, Any]:
        # If answers are already populated by conversational gen_questions, return them directly
        if state.get("answers"):
            return {
                "answers": state["answers"],
                "history": [{"stage": "answer_questions", "n": len(state["answers"])}],
            }
        
        answers: list[dict[str, str]] = []
        for item in state.get("questions", []):
            q = item.get("question", "")
            if self.web_search_fn:
                try:
                    web = self.web_search_fn(q)
                    ctx = "\n\n".join(web) if web else "(no web results)"
                    ans = str(
                        self.llm.invoke(
                            f"Answer comprehensively using the provided contexts. "
                            f"IMPORTANT: You MUST preserve and include the source URLs or Citations from the contexts in your answer.\n\n"
                            f"# Contexts\n{ctx}\n\n# Q: {q}\nA:"
                        ).content
                    ).strip()
                except Exception as e:
                    ans = f"(web answer failed: {e})"
            else:
                ans = str(
                    self.llm.invoke(f"Answer comprehensively from your knowledge.\n\n# Q: {q}\nA:").content
                ).strip()
            answers.append({"question": q, "answer": ans})
        return {
            "answers": answers,
            "history": [{"stage": "answer_questions", "n": len(answers)}],
        }

    def _build_outline(self, state: STORMState) -> dict[str, Any]:
        import json
        # Stage 1: Generate draft outline from topic alone
        try:
            draft_o = self._outline.invoke(
                f"Build a draft 3-5 section outline for an article on the topic: '{state.get('topic', '')}'. "
                f"Each section should have a title and 3-6 key points to cover."
            )
            draft_sections = [{"title": s.title, "key_points": list(s.key_points)} for s in draft_o.sections]
            draft_str = json.dumps(draft_sections, indent=2)
        except Exception as e:
            logger.warning(f"[ARCH::STORM] Draft outline generation failed: {e}")
            draft_str = "(no draft outline available)"

        # Stage 2: Refine and expand the draft outline using the simulated conversations
        qa_block = "\n\n".join(f"Q: {a['question']}\nA: {a['answer']}" for a in state.get("answers", []))
        try:
            o = self._outline.invoke(
                f"# Topic\n{state.get('topic', '')}\n\n"
                f"# Draft Outline\n{draft_str}\n\n"
                f"# Research Q&A\n{qa_block}\n\n"
                f"Refine and expand the Draft Outline using the Research Q&A. "
                f"Add relevant sub-points or sections to make it comprehensive. "
                f"Output a refined outline with 3-5 sections."
            )
            sections = [{"title": s.title, "key_points": list(s.key_points)} for s in o.sections]
        except Exception as e:
            logger.warning(f"[ARCH::STORM] Refined outline generation failed: {e}")
            if 'draft_sections' in locals() and draft_sections:
                sections = draft_sections
            else:
                sections = []
                
        return {
            "outline": sections,
            "history": [{"stage": "outline", "n_sections": len(sections)}],
        }

    def _write_article(self, state: STORMState) -> dict[str, Any]:
        sections: list[dict[str, str]] = []
        qa_block = "\n\n".join(f"Q: {a['question']}\nA: {a['answer']}" for a in state.get("answers", []))
        for sec in state.get("outline", []):
            try:
                w = self._writer.invoke(
                    f"# Topic\n{state.get('topic', '')}\n\n"
                    f"# Section to write\nTitle: {sec['title']}\nKey points: {sec['key_points']}\n\n"
                    f"# Research Q&A available\n{qa_block}\n\n"
                    "Write 2-4 paragraphs of polished prose for this section. "
                    "CRITICAL REQUIREMENT: You MUST include inline citations (e.g. [1], [2]) at the end of every "
                    "claim or fact that references the sources provided in the Research Q&A."
                )
                sections.append({"title": w.title, "body": w.body})
            except Exception as e:
                sections.append({"title": sec["title"], "body": f"(section write failed: {e})"})
        
        # Concatenate final sections
        final_sections_text = "\n\n".join(f"## {s['title']}\n\n{s['body']}" for s in sections)
        
        # Deduplication Step
        try:
            dedup_prompt = (
                f"# Topic\n{state.get('topic', '')}\n\n"
                f"# Concatenated Article\n{final_sections_text}\n\n"
                f"Improve the coherence of the article and remove any duplicate/repeating information between sections. "
                f"Do NOT invent new facts. Keep all inline citations (e.g. [1], [2]) intact. "
                f"Return the polished, deduplicated article sections, keeping the original headings (## Section Title)."
            )
            deduped_text = str(self.llm.invoke(dedup_prompt).content).strip()
        except Exception as e:
            logger.warning(f"[ARCH::STORM] Deduplication failed: {e}")
            deduped_text = final_sections_text
            
        # Lead Section (Summary) Generation
        try:
            summary_prompt = (
                f"# Topic\n{state.get('topic', '')}\n\n"
                f"# Article\n{deduped_text}\n\n"
                f"Write a concise lead section (summary) for the article suitable for the beginning of a Wikipedia-like article. "
                f"It should broadly summarize the key sections in 1-2 paragraphs. "
                f"Include relevant inline citations if summarizing cited facts."
            )
            lead_section = str(self.llm.invoke(summary_prompt).content).strip()
        except Exception as e:
            logger.warning(f"[ARCH::STORM] Lead section generation failed: {e}")
            lead_section = f"Artikel ini membahas tentang {state.get('topic', '')}."
            
        # Final answer with Lead Section
        final_answer = f"# {state.get('topic', '')}\n\n{lead_section}\n\n{deduped_text}"
        
        return {
            "article_sections": sections,
            "final_answer": final_answer,
            "history": [{"stage": "write_article", "n_sections": len(sections)}],
        }

    def run(self, task: str, **kwargs: Any) -> ArchitectureResult:
        graph = self.build()
        config = {
            "recursion_limit": 30,
            "run_name": "StormWorkflow",
        }
        callbacks = kwargs.get("callbacks")
        if callbacks:
            config["callbacks"] = callbacks

        final_state = graph.invoke({"topic": task}, config=config)

        perspectives = final_state.get("perspectives", [])
        questions = final_state.get("questions", [])
        outline = final_state.get("outline", [])
        final_answer = final_state.get("final_answer", "")

        return ArchitectureResult(
            output=final_answer,
            state={
                "n_perspectives": len(perspectives),
                "n_questions": len(questions),
                "n_sections": len(outline),
            },
            trace=final_state.get("history", []),
            metadata={
                "n_perspectives": len(perspectives),
                "n_questions": len(questions),
                "n_sections": len(outline),
                "article_chars": len(final_answer),
                "perspectives": perspectives,
                "questions": questions,
                "answers": final_state.get("answers", []),
                "outline": outline,
            },
        )


def create_storm_workflow(callbacks: list | None = None, language: str = "id", model_name: str | None = None) -> TraceableSTORM:
    """
    Create and return a configured TraceableSTORM instance.

    The returned object exposes .run(task: str, callbacks=callbacks) -> ArchitectureResult,
    which the API router calls directly. No LangGraph graph is compiled
    here -- that happens lazily inside arch.run() via arch.build().

    Configuration:
        n_perspectives:           3 (DEFAULT_N_PERSPECTIVES -- notebook value)
        questions_per_perspective: 2 (DEFAULT_QUESTIONS_PER_PERSPECTIVE -- notebook value)
        web_search_fn:            Research integrations (LightRAG + WebSearch)

    Args:
        callbacks: Optional LangChain callbacks.
        language: Language code for web search.
        model_name: Override model name (e.g. 'gemma4:e4b' for Ollama).

    Returns:
        TraceableSTORM instance ready to call .run(task).
    """
    llm = _build_llm(callbacks=callbacks, model_override=model_name)
    web_search_fn = _build_web_search_fn(language=language, model_name=model_name)

    arch = TraceableSTORM(
        llm=llm,
        n_perspectives=DEFAULT_N_PERSPECTIVES,
        questions_per_perspective=DEFAULT_QUESTIONS_PER_PERSPECTIVE,
        web_search_fn=web_search_fn,
    )

    logger.info(
        "[ARCH::STORM] Workflow ready. "
        f"n_perspectives={DEFAULT_N_PERSPECTIVES}, "
        f"questions_per_perspective={DEFAULT_QUESTIONS_PER_PERSPECTIVE}, "
        f"web_search={'enabled' if web_search_fn else 'disabled'}"
    )
    return arch
