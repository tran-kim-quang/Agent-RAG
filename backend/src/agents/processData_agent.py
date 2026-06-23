import os

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from backend.src.tools.processData_tool import process_data_tool

load_dotenv()

_SYSTEM_PROMPT = (
    "You are a data ingestion specialist. "
    "Your job is to ingest one uploaded document into the knowledge base. "
    "Always use process_data_tool when the frontend provides an uploaded file name and base64 file content. "
    "Confirm where the raw file was stored, where the processed markdown was written, "
    "and how many chunks were indexed into Neo4j."
)

process_data_agent = create_react_agent(
    model=ChatOpenAI(
        model=os.getenv("LLM_MODEL_NAME"),
        api_key=os.getenv("OLLAMA_API_KEY"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
    ),
    tools=[process_data_tool],
    prompt=_SYSTEM_PROMPT,
    name="process_data_agent",
)


@tool
def process_data_agent_tool(file_name: str, file_content_base64: str) -> str:
    """Ingest one uploaded raw file into the document knowledge base."""
    return process_data_tool.invoke(
        {
            "file_name": file_name,
            "file_content_base64": file_content_base64,
        }
    )
