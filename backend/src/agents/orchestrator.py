import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from backend.src.agents.retrieval_agent import retrieval_agent_tool

load_dotenv()

_SYSTEM_PROMPT = (
    "You are an intelligent assistant that answers questions based on a knowledge base of documents. "
    "Use the retrieval_agent tool to search for relevant document content whenever the user asks a question. "
    "Always provide clear, accurate answers grounded in the retrieved documents and cite your sources."
)

orchestrator = create_react_agent(
    model=ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME"),
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
    ),
    tools=[retrieval_agent_tool],
    prompt=_SYSTEM_PROMPT,
    name="orchestrator",
)


def run(query: str) -> str:
    """Run the full multi-agent pipeline with a user query.

    Args:
        query: The user's question about Vietnamese legal documents.

    Returns:
        The orchestrator's final answer.
    """
    result = orchestrator.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content
