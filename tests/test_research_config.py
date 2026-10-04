from settings import ResearchConfig


def test_openrouter_web_search_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ENABLE_WEB_SEARCH", "false")

    assert ResearchConfig.openrouter_web_search_enabled() is False


def test_lightrag_ingestion_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LIGHTRAG_INGEST_ENABLED", raising=False)

    import importlib
    import settings

    settings = importlib.reload(settings)

    assert settings.LightRAGConfig.INGEST_ENABLED is False


def test_finalize_ingestion_does_not_create_client_when_disabled(monkeypatch):
    import asyncio
    import workflows.story_agent.agents.researcher as researcher_module

    agent = researcher_module.ResearchAgent.__new__(researcher_module.ResearchAgent)
    agent.lightrag = None
    monkeypatch.setattr(researcher_module.LightRAGConfig, "INGEST_ENABLED", False)

    def fail_if_called(_language):
        raise AssertionError("LightRAG client must not be created when ingestion is disabled")

    monkeypatch.setattr(researcher_module, "INTEGRATIONS_AVAILABLE", True)
    monkeypatch.setattr(
        "workflows.story_agent.integrations.lightrag_client.get_lightrag_client",
        fail_if_called,
    )

    result = asyncio.run(
        agent.finalize_ingestion(
            {
                "language": "id",
                "research_sources": [{"title": "source", "uri": "https://example.test"}],
                "final_story": "story",
            }
        )
    )

    assert result == {}
