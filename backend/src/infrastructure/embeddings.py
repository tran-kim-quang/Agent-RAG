import os
from functools import lru_cache

from langchain_community.embeddings import OllamaEmbeddings


@lru_cache(maxsize=1)
def get_ollama_embeddings() -> OllamaEmbeddings:
    base_url = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/v1").replace("/v1", "")
    return OllamaEmbeddings(model=os.getenv("EMBEDDING_MODEL_NAME"), base_url=base_url)
