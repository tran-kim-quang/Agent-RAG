from typing import Callable

from langchain_community.embeddings import OllamaEmbeddings

from backend.src.core.models import ChunkRecord
from backend.src.infrastructure import create_neo4j_driver, get_ollama_embeddings


ProgressCallback = Callable[[str, str, dict | None], None]


def _emit_progress(
    callback: ProgressCallback | None,
    phase: str,
    message: str,
    details: dict | None = None,
) -> None:
    if callback is not None:
        callback(phase, message, details)


class Neo4jGraphIndexer:
    def __init__(
        self,
        embeddings_factory: Callable[[], OllamaEmbeddings] = get_ollama_embeddings,
        driver_factory: Callable[[], object] | None = None,
        owner_id: str = "system",
    ) -> None:
        self._embeddings_factory = embeddings_factory
        self._driver_factory = driver_factory or self._default_driver_factory
        self._owner_id = owner_id

    def build_index(
        self,
        chunks: list[ChunkRecord],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        valid_chunks = [chunk for chunk in chunks if chunk.content.strip()]
        if not valid_chunks:
            return

        source = valid_chunks[0].metadata.get("source", "")
        metadata = valid_chunks[0].metadata
        embeddings_model = self._embeddings_factory()
        texts = [chunk.content for chunk in valid_chunks]
        _emit_progress(
            progress_callback,
            "embed",
            f"Generating embeddings for {len(valid_chunks)} chunks",
            {"total_chunks": len(valid_chunks), "indexed_chunks": 0, "source": source},
        )
        vectors = embeddings_model.embed_documents(texts)
        dims = len(vectors[0])

        driver = self._driver_factory()
        with driver.session() as session:
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

            total_chunks = len(valid_chunks)
            for index, (chunk, vector) in enumerate(zip(valid_chunks, vectors), start=1):
                chunk_id = (
                    f"{chunk.metadata.get('source', '')}_{chunk.metadata.get('chunk_index', 0)}"
                )
                session.run(
                    """
                    MERGE (d:Document {source: $source, owner_id: $owner_id})
                    SET d.name                    = $document_name,
                        d.raw_source              = $raw_source,
                        d.processed_metadata_path = $processed_metadata_path,
                        d.original_file_name      = $original_file_name,
                        d.source_type             = $source_type,
                        d.updated_at              = datetime(),
                        d.chunk_count             = $total_chunks
                    MERGE (c:Chunk {id: $id, owner_id: $owner_id})
                    SET c.text        = $text,
                        c.source      = $source,
                        c.chunk_index = $chunk_index,
                        c.updated_at  = datetime()
                    MERGE (d)-[:HAS_CHUNK]->(c)
                    WITH c, d
                    CALL db.create.setNodeVectorProperty(c, 'embedding', $embedding)
                    """,
                    id=chunk_id,
                    text=chunk.content,
                    source=chunk.metadata.get("source", ""),
                    owner_id=self._owner_id,
                    chunk_index=chunk.metadata.get("chunk_index", 0),
                    document_name=chunk.metadata.get("name", ""),
                    raw_source=chunk.metadata.get("raw_source", ""),
                    processed_metadata_path=chunk.metadata.get("processed_metadata_path", ""),
                    original_file_name=chunk.metadata.get("original_file_name", ""),
                    source_type=chunk.metadata.get("source_type", ""),
                    total_chunks=total_chunks,
                    embedding=vector,
                )
                if index == 1 or index == total_chunks or index % 10 == 0:
                    _emit_progress(
                        progress_callback,
                        "index",
                        f"Indexed {index}/{total_chunks} chunks into Neo4j",
                        {
                            "indexed_chunks": index,
                            "total_chunks": total_chunks,
                            "source": source,
                            "raw_source": metadata.get("raw_source", ""),
                            "processed_metadata_path": metadata.get("processed_metadata_path", ""),
                        },
                    )

            session.run(
                """
                MATCH (a:Chunk {source: $source, owner_id: $owner_id}),
                      (b:Chunk {source: $source, owner_id: $owner_id})
                WHERE b.chunk_index = a.chunk_index + 1
                MERGE (a)-[:NEXT_CHUNK]->(b)
                """,
                source=source,
                owner_id=self._owner_id,
            )

            session.run(
                """
                MATCH (d:Document {source: $source, owner_id: $owner_id})-[:HAS_CHUNK]->(c:Chunk)
                WITH d, count(c) AS indexed_chunks
                SET d.indexed_chunks = indexed_chunks,
                    d.updated_at = datetime()
                """,
                source=source,
                owner_id=self._owner_id,
            )

        _emit_progress(
            progress_callback,
            "index_complete",
            f"Finished graph indexing for {source}",
            {"indexed_chunks": len(valid_chunks), "total_chunks": len(valid_chunks), "source": source},
        )
        driver.close()

    @staticmethod
    def _default_driver_factory():
        return create_neo4j_driver()


class Neo4jGraphRepository:
    def __init__(self, driver_factory: Callable[[], object] | None = None) -> None:
        self._driver_factory = driver_factory or Neo4jGraphIndexer._default_driver_factory

    def list_documents(self, limit: int = 20, owner_id: str | None = None) -> list[dict]:
        driver = self._driver_factory()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (c:Chunk)
                WHERE $owner_id IS NULL OR c.owner_id = $owner_id
                WITH c.source AS source, c.owner_id AS owner_id,
                     count(c) AS actual_chunk_nodes, max(c.updated_at) AS chunk_updated_at
                OPTIONAL MATCH (d:Document {source: source, owner_id: owner_id})
                RETURN
                    source AS source,
                    owner_id AS owner_id,
                    coalesce(d.name, source) AS name,
                    d.raw_source AS raw_source,
                    d.original_file_name AS original_file_name,
                    d.source_type AS source_type,
                    coalesce(d.chunk_count, actual_chunk_nodes) AS chunk_count,
                    coalesce(d.indexed_chunks, actual_chunk_nodes) AS indexed_chunks,
                    toString(coalesce(d.updated_at, chunk_updated_at)) AS updated_at
                ORDER BY coalesce(d.updated_at, chunk_updated_at) DESC
                LIMIT $limit
                """,
                limit=limit,
                owner_id=owner_id,
            )
            documents = [dict(record) for record in result]
        driver.close()
        return documents

    def get_document_graph(self, source: str, limit_chunks: int = 18, owner_id: str | None = None) -> dict:
        driver = self._driver_factory()
        with driver.session() as session:
            doc_result = session.run(
                """
                OPTIONAL MATCH (d:Document {source: $source})
                WHERE $owner_id IS NULL OR d.owner_id = $owner_id
                OPTIONAL MATCH (c:Chunk {source: $source})
                WHERE $owner_id IS NULL OR c.owner_id = $owner_id
                WITH d, count(c) AS actual_chunk_nodes, max(c.updated_at) AS chunk_updated_at
                RETURN
                    $source AS source,
                    coalesce(d.owner_id, $owner_id) AS owner_id,
                    coalesce(d.name, $source) AS name,
                    d.raw_source AS raw_source,
                    d.original_file_name AS original_file_name,
                    d.source_type AS source_type,
                    coalesce(d.chunk_count, actual_chunk_nodes) AS chunk_count,
                    coalesce(d.indexed_chunks, actual_chunk_nodes) AS indexed_chunks,
                    toString(coalesce(d.updated_at, chunk_updated_at)) AS updated_at,
                    actual_chunk_nodes AS actual_chunk_nodes
                """,
                source=source,
                owner_id=owner_id,
            ).single()

            if doc_result is None or doc_result["actual_chunk_nodes"] == 0:
                driver.close()
                return {
                    "document": None,
                    "nodes": [],
                    "edges": [],
                }

            chunk_result = session.run(
                """
                MATCH (c:Chunk {source: $source})
                WHERE $owner_id IS NULL OR c.owner_id = $owner_id
                RETURN
                    c.id AS id,
                    c.chunk_index AS chunk_index,
                    left(c.text, 180) AS preview
                ORDER BY c.chunk_index ASC
                LIMIT $limit_chunks
                """,
                source=source,
                limit_chunks=limit_chunks,
                owner_id=owner_id,
            )
            nodes = [dict(record) for record in chunk_result]

            edge_result = session.run(
                """
                MATCH (a:Chunk {source: $source})-[:NEXT_CHUNK]->(b:Chunk {source: $source})
                WHERE $owner_id IS NULL OR (a.owner_id = $owner_id AND b.owner_id = $owner_id)
                RETURN
                    a.id AS source_id,
                    b.id AS target_id
                ORDER BY a.chunk_index ASC
                LIMIT $limit_edges
                """,
                source=source,
                limit_edges=max(limit_chunks - 1, 0),
                owner_id=owner_id,
            )
            edges = [dict(record) for record in edge_result]

        driver.close()
        return {
            "document": dict(doc_result),
            "nodes": nodes,
            "edges": edges,
        }

    def delete_document(self, source: str, owner_id: str) -> bool:
        driver = self._driver_factory()
        try:
            with driver.session() as session:
                result = session.run(
                    """
                    OPTIONAL MATCH (d:Document {source: $source, owner_id: $owner_id})
                    WITH [node IN collect(d) WHERE node IS NOT NULL] AS documents
                    OPTIONAL MATCH (c:Chunk {source: $source, owner_id: $owner_id})
                    WITH documents, [node IN collect(c) WHERE node IS NOT NULL] AS chunks
                    FOREACH (document IN documents | DETACH DELETE document)
                    FOREACH (chunk IN chunks | DETACH DELETE chunk)
                    RETURN size(documents) + size(chunks) AS deleted
                    """,
                    source=source,
                    owner_id=owner_id,
                ).single()
                return result is not None and int(result["deleted"]) > 0
        finally:
            driver.close()


def build_graph_index(
    chunks: list[dict],
    progress_callback: ProgressCallback | None = None,
) -> None:
    indexer = Neo4jGraphIndexer()
    indexer.build_index([ChunkRecord.from_dict(chunk) for chunk in chunks], progress_callback=progress_callback)
