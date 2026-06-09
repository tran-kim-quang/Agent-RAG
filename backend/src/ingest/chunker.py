import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

load_dotenv()

_embeddings = None

def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=os.getenv("LLM_MODEL_CHUNKER"),
            openai_api_key=os.getenv("OLLAMA_API_KEY"),
            openai_api_base=os.getenv("OLLAMA_BASE_URL"),
        )
    return _embeddings


def chunk_document(doc: dict) -> list[dict]:
    splitter = SemanticChunker(
        embeddings=_get_embeddings(),
        breakpoint_threshold_type="percentile",
    )
    chunks = splitter.create_documents([doc["content"]])
    return [
        {
            "content": chunk.page_content,
            "metadata": {**doc["metadata"], "chunk_index": i},
        }
        for i, chunk in enumerate(chunks)
    ]


def chunk_documents(documents: list[dict]) -> list[dict]:
    result = []
    for doc in documents:
        result.extend(chunk_document(doc))
    return result
