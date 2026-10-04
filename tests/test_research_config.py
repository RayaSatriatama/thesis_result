from settings import ResearchConfig


def test_openrouter_web_search_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("OPENROUTER_ENABLE_WEB_SEARCH", "false")

    assert ResearchConfig.openrouter_web_search_enabled() is False
