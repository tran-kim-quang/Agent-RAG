import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain_community.graphs import Neo4jGraph
from langchain.schema import Document

load_dotenv()

_CONFIG_PATH = Path(__file__).parents[2] / "configs" / "config.yaml"

def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_NAME"),
        openai_api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
        openai_api_base=os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/v1"),
    )


def _neo4j_conn() -> dict:
    return {
        "url": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "username": os.getenv("NEO4J_USERNAME", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", "password"),
    }


def build_graph_index(chunks: list[dict]) -> Neo4jVector:
    """
    Store chunks as Document nodes in Neo4j with vector embeddings.
    Returns a Neo4jVector retriever.
    """
    config = _load_config()
    chunk_size = config["chunking"]["chunk_size"]

    docs = [
        Document(
            page_content=chunk["content"],
            metadata=chunk["metadata"],
        )
        for chunk in chunks
        if chunk["content"].strip()
    ]

    conn = _neo4j_conn()
    vector_store = Neo4jVector.from_documents(
        documents=docs,
        embedding=_get_embeddings(),
        url=conn["url"],
        username=conn["username"],
        password=conn["password"],
        index_name="document_chunks",
        node_label="Chunk",
        text_node_property="text",
        embedding_node_property="embedding",
        pre_delete_collection=False,
    )

    # Build NEXT_CHUNK relationships between consecutive chunks from the same source
    graph = Neo4jGraph(
        url=conn["url"],
        username=conn["username"],
        password=conn["password"],
    )
    graph.query("""
        MATCH (a:Chunk), (b:Chunk)
        WHERE a.source = b.source
          AND b.chunk_index = a.chunk_index + 1
        MERGE (a)-[:NEXT_CHUNK]->(b)
    """)

    return vector_store


def load_graph_index() -> Neo4jVector:
    """Load an existing Neo4j vector index without re-ingesting."""
    conn = _neo4j_conn()
    return Neo4jVector.from_existing_index(
        embedding=_get_embeddings(),
        url=conn["url"],
        username=conn["username"],
        password=conn["password"],
        index_name="document_chunks",
        text_node_property="text",
        embedding_node_property="embedding",
    )
