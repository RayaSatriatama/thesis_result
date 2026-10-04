import asyncio


def test_openrouter_dispatches_to_searxng_when_configured(monkeypatch):
    import workflows.story_agent.agents.researcher as researcher_module

    agent = researcher_module.ResearchAgent.__new__(researcher_module.ResearchAgent)
    agent._is_openrouter = True
    agent._openrouter_api_key = "configured"

    async def fake_searxng(query, language, theme):
        return "searx context", [{"uri": "https://example.test"}]

    async def fail_openrouter(query, language, theme):
        raise AssertionError("OpenRouter search must not be used")

    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "searxng")
    monkeypatch.setattr(agent, "_search_web_searxng", fake_searxng)
    monkeypatch.setattr(agent, "_search_web_openrouter", fail_openrouter)

    text, sources = asyncio.run(agent._search_web("query", "id", "theme"))

    assert text == "searx context"
    assert sources[0]["uri"] == "https://example.test"
