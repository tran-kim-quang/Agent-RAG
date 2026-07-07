from __future__ import annotations

from typing import Callable

from backend.src.index.graph_index import get_document_graph, list_graph_documents


class GraphQueryService:
    def __init__(
        self,
        list_documents_fn: Callable[[int], list[dict]] = list_graph_documents,
        get_document_graph_fn: Callable[[str, int], dict] = get_document_graph,
    ) -> None:
        self._list_documents_fn = list_documents_fn
        self._get_document_graph_fn = get_document_graph_fn

    def list_documents(self, limit: int = 20) -> list[dict]:
        return self._list_documents_fn(limit)

    def get_document_graph(self, source: str, limit_chunks: int = 18) -> dict:
        return self._get_document_graph_fn(source, limit_chunks)
