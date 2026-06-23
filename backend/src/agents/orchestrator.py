import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from backend.src.agents.processData_agent import process_data_agent_tool
from backend.src.agents.retrieval_agent import retrieval_agent_tool

load_dotenv()

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an intelligent orchestration assistant for a document knowledge base. "
    "Use retrieval_agent_tool when the user asks a question about document content. "
    "Use process_data_agent_tool when the system asks you to ingest an uploaded file into the knowledge base. "
    "Always choose the correct tool for the user's task and return clear, grounded results."
)

orchestrator = create_react_agent(
    model=ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME"),
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
    ),
    tools=[retrieval_agent_tool, process_data_agent_tool],
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
    logger.info("[orchestrator/query] Received query: %s", query)
    result = orchestrator.invoke({"messages": [HumanMessage(content=query)]})
    logger.info("[orchestrator/query] Query handled successfully")
    return result["messages"][-1].content


def ingest_uploaded_document(file_name: str, file_content_base64: str) -> dict:
    """Route uploaded document ingestion through the orchestrator toolchain."""
    logger.info("[orchestrator/ingest] Routing uploaded document: file_name=%s", file_name)
    result = process_data_agent_tool.invoke(
        {
            "file_name": file_name,
            "file_content_base64": file_content_base64,
        }
    )

    lines = [line.strip() for line in result.splitlines() if line.strip()]
    payload = {
        "message": lines[0] if lines else "Processed document successfully.",
    }

    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.lstrip("- ").split(":", 1)
        payload[key.strip()] = value.strip()

    if "chunks_ingested" in payload:
        payload["chunk_count"] = int(payload.pop("chunks_ingested"))

    logger.info("[orchestrator/ingest] Uploaded document handled: payload=%s", payload)
    return payload
