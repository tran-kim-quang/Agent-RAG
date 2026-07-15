from backend.src.tools import research_tools


class _FakeAuthor:
    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self) -> str:
        return self._name


class _FakePaper:
    title = "Agentic Retrieval for Multimodal Documents"
    authors = [_FakeAuthor("Ada Lovelace"), _FakeAuthor("Alan Turing")]
    summary = "A focused summary about retrieval agents and external research fallback."
    entry_id = "https://arxiv.org/abs/2601.00001"


class _FakeArxivClient:
    def results(self, search):
        return [_FakePaper()]


def test_arxiv_tool_formats_paper_results(monkeypatch):
    monkeypatch.setattr(research_tools, "_arxiv_client", _FakeArxivClient())

    result = research_tools.arxiv_tool.invoke({"query": "agentic retrieval"})

    assert "Title: Agentic Retrieval for Multimodal Documents" in result
    assert "Authors: Ada Lovelace, Alan Turing" in result
    assert "URL: https://arxiv.org/abs/2601.00001" in result


def test_wikipedia_tool_is_configured_for_factual_search():
    assert research_tools.wikipedia_tool.name == "wikipedia"
    assert "Search Wikipedia for factual information" in research_tools.wikipedia_tool.description
