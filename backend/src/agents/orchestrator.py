import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from backend.src.monitoring import agent_run_monitor
from backend.src.agents.research_agent import research_agent_tool
from backend.src.agents.retrieval_agent import retrieval_agent_tool
from backend.src.infrastructure.checkpoints import get_postgres_checkpointer

load_dotenv()

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an intelligent orchestration assistant for a document knowledge base. "
    "Use retrieval_agent_tool first when the user asks a question about document content. "
    "Evaluate whether the retrieved information is actually sufficient, relevant, and specific to the query. "
    "If the retrieval output is sparse, low-confidence, off-topic, or clearly insufficient for the user's request, "
    "call research_agent_tool to gather supplemental external research from arXiv and Wikipedia before answering. "
    "When both internal retrieval and external research are used, clearly synthesize them and prefer the internal knowledge base when it directly answers the question. "
    "Always choose the correct tool for the user's task and return clear, grounded results."
)

@lru_cache(maxsize=1)
def get_orchestrator():
    return create_react_agent(
        model=ChatOpenAI(
            model=os.getenv("LLM_MODEL_NAME"),
            api_key=os.getenv("OLLAMA_API_KEY"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
        ),
        tools=[retrieval_agent_tool, research_agent_tool],
        prompt=_SYSTEM_PROMPT,
        name="orchestrator",
        checkpointer=get_postgres_checkpointer(),
    )


def run(
    query: str,
    thread_id: str,
    history: list[dict[str, str]] | None = None,
    token_callback=None,
) -> str:
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
    config = {"configurable": {"thread_id": thread_id}}
    checkpointer = get_postgres_checkpointer()
    if checkpointer.get(config) is None and history:
        messages = [
            HumanMessage(content=item["content"]) if item["role"] == "user" else AIMessage(content=item["content"])
            for item in history
            if item["role"] in {"user", "assistant"}
        ]
    else:
        messages = [HumanMessage(content=query)]
    orchestrator = get_orchestrator()
    for message_chunk, metadata in orchestrator.stream(
        {"messages": messages},
        config=config,
        stream_mode="messages",
    ):
        if token_callback is None or metadata.get("langgraph_node") != "agent":
            continue
        content = _message_text(message_chunk.content)
        if content:
            token_callback(content)
    state = orchestrator.get_state(config)
    final_answer = _message_text(state.values["messages"][-1].content)
    agent_run_monitor.append_event(
        "orchestrator_complete",
        "Orchestrator finished the workflow and returned a final answer.",
        {"answer_length": len(final_answer)},
        status="processing",
    )
    logger.info("[orchestrator/query] Query handled successfully")
    return final_answer


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content or "")
