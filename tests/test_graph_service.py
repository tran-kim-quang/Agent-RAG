from backend.src.services import DocumentDeletionService, GraphQueryService


class FakeGraphRepository:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists
        self.deleted: list[tuple[str, str]] = []

    def list_documents(self, limit: int = 20, owner_id: str | None = None) -> list[dict]:
        return [{"source": "document.json", "owner_id": owner_id}][:limit]

    def get_document_graph(self, source: str, limit_chunks: int = 18, owner_id: str | None = None) -> dict:
        return {"document": {"source": source, "owner_id": owner_id}, "nodes": [], "edges": []}

    def delete_document(self, source: str, owner_id: str) -> bool:
        self.deleted.append((source, owner_id))
        return self.exists


class FakeDocumentRepository:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists
        self.deleted: list[tuple[str, str]] = []

    def upsert_from_upload(self, job) -> None:
        return None

    def delete_by_source(self, user_id: str, source: str) -> bool:
        self.deleted.append((user_id, source))
        return self.exists


class FakeKnowledgeBaseRepository:
    def __init__(self) -> None:
        self.bumped: list[str] = []

    def get_version(self, user_id: str) -> int:
        return 1

    def bump_version(self, user_id: str) -> int:
        self.bumped.append(user_id)
        return 2


def test_graph_query_service_delegates_to_repository() -> None:
    graphs = FakeGraphRepository()
    service = GraphQueryService(graphs)

    assert service.list_documents(1, "user-1")[0]["owner_id"] == "user-1"
    assert service.get_document_graph("document.json", 5, "user-1")["document"]["source"] == "document.json"


def test_document_deletion_removes_owned_data_and_invalidates_cache() -> None:
    graphs = FakeGraphRepository()
    documents = FakeDocumentRepository()
    knowledge_bases = FakeKnowledgeBaseRepository()
    service = DocumentDeletionService(graphs, documents, knowledge_bases)

    assert service.delete("document.json", "user-1") is True
    assert graphs.deleted == [("document.json", "user-1")]
    assert documents.deleted == [("user-1", "document.json")]
    assert knowledge_bases.bumped == ["user-1"]


def test_document_deletion_removes_metadata_when_graph_document_is_missing() -> None:
    documents = FakeDocumentRepository()
    knowledge_bases = FakeKnowledgeBaseRepository()
    service = DocumentDeletionService(FakeGraphRepository(exists=False), documents, knowledge_bases)

    assert service.delete("missing.json", "user-1") is True
    assert documents.deleted == [("user-1", "missing.json")]
    assert knowledge_bases.bumped == ["user-1"]


def test_document_deletion_reports_missing_only_when_both_stores_are_empty() -> None:
    documents = FakeDocumentRepository(exists=False)
    knowledge_bases = FakeKnowledgeBaseRepository()
    service = DocumentDeletionService(FakeGraphRepository(exists=False), documents, knowledge_bases)

    assert service.delete("missing.json", "user-1") is False
    assert knowledge_bases.bumped == []
