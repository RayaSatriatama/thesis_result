"""DeepEval LLM wrapper for using LangChain LLMs with the GEval metric."""
DEEPEVAL_AVAILABLE = False
CriticDeepEvalLLM = None  # type: ignore[assignment]

try:
    from deepeval.models.base_model import DeepEvalBaseLLM

    DEEPEVAL_AVAILABLE = True

    class CriticDeepEvalLLM(DeepEvalBaseLLM):  # type: ignore[no-redef]
        """Wraps a LangChain LLM for compatibility with the DeepEval GEval metric."""

        def __init__(self, llm):
            self.llm = llm

        def load_model(self):
            return self.llm

        def generate(self, prompt: str) -> str:
            return self.llm.invoke(prompt).content

        async def a_generate(self, prompt: str) -> str:
            res = await self.llm.ainvoke(prompt)
            return res.content

        def get_model_name(self) -> str:
            return getattr(self.llm, "model_name", "custom_geval_model")

except ImportError:
    pass
