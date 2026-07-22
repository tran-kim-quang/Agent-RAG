from __future__ import annotations

from backend.src.core.repositories import DocumentRepository, GraphRepository, KnowledgeBaseRepository


class GraphQueryService:
    def __init__(self, graphs: GraphRepository) -> None:
        self._graphs = graphs

    def list_documents(self, limit: int = 20, owner_id: str | None = None) -> list[dict]:
        return self._graphs.list_documents(limit, owner_id)

    def get_document_graph(self, source: str, limit_chunks: int = 18, owner_id: str | None = None) -> dict:
        return self._graphs.get_document_graph(source, limit_chunks, owner_id)


class DocumentDeletionService:
    def __init__(
        self,
        graphs: GraphRepository,
        documents: DocumentRepository,
        knowledge_bases: KnowledgeBaseRepository,
    ) -> None:
        self._graphs = graphs
        self._documents = documents
        self._knowledge_bases = knowledge_bases

    def delete(self, source: str, owner_id: str) -> bool:
        graph_deleted = self._graphs.delete_document(source, owner_id)
        metadata_deleted = self._documents.delete_by_source(owner_id, source)
        if not graph_deleted and not metadata_deleted:
            return False
        self._knowledge_bases.bump_version(owner_id)
        return True
