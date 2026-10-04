import asyncio

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


def test_openrouter_is_the_default_web_search_provider(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_WEB_SEARCH_ENGINE", raising=False)

    import importlib
    import settings

    settings = importlib.reload(settings)

    assert settings.ResearchConfig.web_search_provider() == "openrouter"
    assert settings.ResearchConfig.openrouter_web_search_engine() == "exa"


def test_web_search_can_be_disabled_globally(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")

    import importlib
    import settings

    settings = importlib.reload(settings)

    assert settings.ResearchConfig.web_search_enabled() is False


def test_openrouter_search_uses_the_server_tool_and_parses_citations(monkeypatch):
    import workflows.story_agent.agents.researcher as researcher_module

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "PSLV-C56 launched from Sriharikota.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url_citation": {
                                        "url": "https://www.isro.gov.in/mission",
                                        "title": "ISRO mission",
                                        "content": "Official launch record",
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

    class Client:
        def __init__(self, **_kwargs):
            self.payload = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, *, headers, json):
            assert headers["Authorization"] == "Bearer configured-key"
            self.payload = json
            clients.append(self)
            return Response()

    clients = []
    agent = researcher_module.ResearchAgent.__new__(researcher_module.ResearchAgent)
    agent._is_openrouter = True
    agent._openrouter_api_key = "configured-key"
    agent._openrouter_base_url = "https://openrouter.example/api/v1"
    agent.model_name = "openai/gpt-4o-mini"
    monkeypatch.setattr(
        researcher_module,
        "get_registry",
        lambda: type("Registry", (), {"get": lambda *_args: "Search: {query}"})(),
    )
    monkeypatch.setattr(researcher_module.httpx, "AsyncClient", Client)
    monkeypatch.setenv("OPENROUTER_WEB_SEARCH_ENGINE", "exa")
    monkeypatch.setenv("OPENROUTER_WEB_SEARCH_MAX_RESULTS", "3")
    monkeypatch.setenv("OPENROUTER_WEB_SEARCH_MAX_TOTAL_RESULTS", "3")
    monkeypatch.setenv("OPENROUTER_WEB_SEARCH_MAX_USES", "1")
    monkeypatch.setenv("OPENROUTER_WEB_SEARCH_MAX_CHARACTERS", "800")
    monkeypatch.setenv(
        "OPENROUTER_PROVIDER_PREFERENCES",
        '{"only":["openai"],"allow_fallbacks":false}',
    )

    text, sources = asyncio.run(
        agent._search_web_openrouter("PSLV-C56 launch", "English", "space")
    )

    assert text == "PSLV-C56 launched from Sriharikota."
    assert sources == [
        {
            "uri": "https://www.isro.gov.in/mission",
            "title": "ISRO mission",
            "snippet": "Official launch record",
        }
    ]
    payload = clients[0].payload
    assert "plugins" not in payload
    assert payload["tools"] == [
        {
            "type": "openrouter:web_search",
            "parameters": {
                "engine": "exa",
                "max_results": 3,
                "max_total_results": 3,
                "max_uses": 1,
                "max_characters": 800,
            },
        }
    ]
    assert payload["max_tool_calls"] == 1
    assert payload["provider"] == {
        "only": ["openai"],
        "allow_fallbacks": False,
    }
