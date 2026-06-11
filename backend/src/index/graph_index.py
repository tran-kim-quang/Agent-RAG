import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_community.embeddings import OllamaEmbeddings

load_dotenv()

_CONFIG_PATH = Path(__file__).parents[2] / "configs" / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _get_embeddings() -> OllamaEmbeddings:
    base_url = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434/v1").replace("/v1", "")
    return OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_NAME"),
        base_url=base_url,
    )


def _neo4j_conn() -> dict:
    return {
        "url": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "username": os.getenv("NEO4J_USERNAME", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", "password"),
    }


def build_graph_index(chunks: list[dict]) -> None:
    """Embed chunks and store them in Neo4j with a vector index."""
    valid_chunks = [c for c in chunks if c["content"].strip()]
    if not valid_chunks:
        return

    embeddings_model = _get_embeddings()
    texts = [c["content"] for c in valid_chunks]
    vectors = embeddings_model.embed_documents(texts)
    dims = len(vectors[0])

    conn = _neo4j_conn()
    driver = GraphDatabase.driver(conn["url"], auth=(conn["username"], conn["password"]))

    with driver.session() as session:
        # Create vector index (idempotent)
        session.run(
            """
            CREATE VECTOR INDEX document_chunks IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: $dims,
                `vector.similarity_function`: 'cosine'
            }}
            """,
            dims=dims,
        )

        # Upsert each chunk node
        for chunk, vector in zip(valid_chunks, vectors):
            chunk_id = (
                f"{chunk['metadata'].get('source', '')}_{chunk['metadata'].get('chunk_index', 0)}"
            )
            session.run(
                """
                MERGE (c:Chunk {id: $id})
                SET c.text        = $text,
                    c.source      = $source,
                    c.chunk_index = $chunk_index
                WITH c
                CALL db.create.setNodeVectorProperty(c, 'embedding', $embedding)
                """,
                id=chunk_id,
                text=chunk["content"],
                source=chunk["metadata"].get("source", ""),
                chunk_index=chunk["metadata"].get("chunk_index", 0),
                embedding=vector,
            )

        # Link consecutive chunks from the same source
        session.run(
            """
            MATCH (a:Chunk), (b:Chunk)
            WHERE a.source = b.source
              AND b.chunk_index = a.chunk_index + 1
            MERGE (a)-[:NEXT_CHUNK]->(b)
            """
        )

    driver.close()
