"""Runtime preflight for the optional DeepEval-based G-Eval metric."""

from workflows.story_agent.agents.critic.deepeval_llm import DEEPEVAL_AVAILABLE


def test_geval_dependency_is_available_in_runtime_environment() -> None:
    """A configured G-Eval metric must not be silently skipped at runtime."""
    assert DEEPEVAL_AVAILABLE is True
