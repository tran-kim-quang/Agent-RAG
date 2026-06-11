import os
from dotenv import load_dotenv
from langchain_community.embeddings import OllamaEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

load_dotenv()

_embeddings = None

def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        base_url = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/v1").replace("/v1", "")
        _embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDING_MODEL_NAME"),
            base_url=base_url,
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
