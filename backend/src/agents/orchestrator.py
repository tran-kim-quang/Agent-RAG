import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from backend.src.monitoring import agent_run_monitor
from backend.src.agents.processData_agent import process_data_agent_tool
from backend.src.agents.retrieval_agent import retrieval_agent_tool
from backend.src.tools.processData_tool import _decode_uploaded_content, process_and_ingest_uploaded_file

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
    agent_run_monitor.append_event(
        "orchestrator_start",
        "Orchestrator is deciding which agent tools to call.",
        {"query_length": len(query)},
        status="processing",
    )
    result = orchestrator.invoke({"messages": [HumanMessage(content=query)]})
    final_answer = result["messages"][-1].content
    agent_run_monitor.append_event(
        "orchestrator_complete",
        "Orchestrator finished the workflow and returned a final answer.",
        {"answer_length": len(final_answer)},
        status="processing",
    )
    logger.info("[orchestrator/query] Query handled successfully")
    return final_answer


def ingest_uploaded_document(file_name: str, file_content_base64: str) -> dict:
    """Handle uploaded document ingestion with a structured result."""
    logger.info("[orchestrator/ingest] Routing uploaded document: file_name=%s", file_name)
    file_bytes = _decode_uploaded_content(file_content_base64)
    payload = process_and_ingest_uploaded_file(file_name, file_bytes)
    payload["message"] = f"Processed '{payload['source_name']}' successfully."
    logger.info("[orchestrator/ingest] Uploaded document handled: payload=%s", payload)
    return payload
