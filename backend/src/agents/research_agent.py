import os

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from backend.src.monitoring import agent_run_monitor
from backend.src.tools.research_tools import arxiv_tool, wikipedia_tool

load_dotenv()

_SYSTEM_PROMPT = (
    "You are an external research specialist for a document RAG system. "
    "Use arxiv for academic and technical research papers. "
    "Use wikipedia for broad factual background, definitions, entities, timelines, and general context. "
    "Use both tools when the query benefits from academic depth plus factual background. "
    "Return a concise synthesis with source URLs or source names from the tools. "
    "Do not invent citations, and clearly say when the tools do not find enough information."
)

research_agent = create_react_agent(
    model=ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME"),
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
    ),
    tools=[arxiv_tool, wikipedia_tool],
    prompt=_SYSTEM_PROMPT,
    name="research_agent",
)


@tool
def research_agent_tool(query: str) -> str:
    """Research outside the document database using arXiv and Wikipedia.

    Use this when document retrieval is sparse, off-topic, outdated, or insufficient
    to answer the user's question.
    """
    agent_run_monitor.append_event(
        "research_agent_start",
        "Research agent is gathering external context from arXiv and Wikipedia.",
        {"query_length": len(query)},
        status="processing",
    )
    try:
        result = research_agent.invoke({"messages": [HumanMessage(content=query)]})
    except Exception as exc:
        agent_run_monitor.append_event(
            "research_agent_failed",
            "Research agent was unavailable.",
            {"error": str(exc)},
            status="failed",
        )
        return f"Research agent unavailable: {exc}"

    answer = result["messages"][-1].content
    agent_run_monitor.append_event(
        "research_agent_complete",
        "Research agent completed external context gathering.",
        {"answer_length": len(answer)},
        status="processing",
    )
    return answer
