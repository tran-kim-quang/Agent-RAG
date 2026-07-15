from importlib import import_module


research_agent_module = import_module("backend.src.agents.research_agent")


def test_research_agent_tool_returns_clear_error_when_llm_fails(monkeypatch):
    class _FailingResearchAgent:
        def invoke(self, payload):
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(research_agent_module, "research_agent", _FailingResearchAgent())

    result = research_agent_module.research_agent_tool.invoke({"query": "retrieval augmented generation"})

    assert result == "Research agent unavailable: LLM unavailable"
