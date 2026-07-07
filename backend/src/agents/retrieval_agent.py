import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent

from backend.src.monitoring import agent_run_monitor
from backend.src.tools.retrieval_tool import graph_search_tool

load_dotenv()

_SYSTEM_PROMPT = (
    "You are a document retrieval specialist. "
    "Your job is to find relevant information from the document database. "
    "Always use graph_search_tool to find relevant document chunks based on the user's query. "
    "Return comprehensive, accurate information from the documents you find, "
    "including source references."
)

retrieval_agent = create_react_agent(
    model=ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME"),
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
    ),
    tools=[graph_search_tool],
    prompt=_SYSTEM_PROMPT,
    name="retrieval_agent",
)


@tool
def retrieval_agent_tool(query: str) -> str:
    """Retrieve relevant information from the document database.

    Searches indexed documents for information relevant to the query.
    Use this when you need to look up content from the knowledge base.

    Args:
        query: The search query.

    Returns:
        Relevant document excerpts with source information.
    """
    agent_run_monitor.append_event(
        "retrieval_agent_start",
        "Retrieval agent is analyzing the user question.",
        {"query_length": len(query)},
        status="processing",
    )
    result = retrieval_agent.invoke({"messages": [HumanMessage(content=query)]})
    answer = result["messages"][-1].content
    agent_run_monitor.append_event(
        "retrieval_agent_complete",
        "Retrieval agent completed context gathering.",
        {"answer_length": len(answer)},
        status="processing",
    )
    return answer
