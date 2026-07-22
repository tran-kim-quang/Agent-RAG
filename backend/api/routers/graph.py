from fastapi import APIRouter, HTTPException

from backend.api.dependencies import CurrentUser, document_deletions, graph_queries
from backend.api.presenters import clamp_limit
from backend.api.schemas import GraphDocumentResponse, GraphOverviewResponse, MessageResponse
from backend.src.core.roles import is_admin

router = APIRouter(prefix="/api/graph")


@router.get("/documents", response_model=GraphOverviewResponse)
def documents(user: CurrentUser, limit: int = 20) -> GraphOverviewResponse:
    owner_id = None if is_admin(user.role) else user.id
    return GraphOverviewResponse(documents=graph_queries.list_documents(clamp_limit(limit), owner_id))


@router.get("/document", response_model=GraphDocumentResponse)
def document(user: CurrentUser, source: str, limit_chunks: int = 18, owner_id: str | None = None) -> GraphDocumentResponse:
    target_owner_id = owner_id if is_admin(user.role) and owner_id else (None if is_admin(user.role) else user.id)
    payload = graph_queries.get_document_graph(source, clamp_limit(limit_chunks), target_owner_id)
    if payload.get("document") is None: raise HTTPException(status_code=404, detail="Graph document not found.")
    return GraphDocumentResponse(**payload)


@router.delete("/document", response_model=MessageResponse)
def delete_document(user: CurrentUser, source: str, owner_id: str | None = None) -> MessageResponse:
    target_owner_id = owner_id if is_admin(user.role) and owner_id else user.id
    if not document_deletions.delete(source, target_owner_id):
        raise HTTPException(status_code=404, detail="Graph document not found.")
    return MessageResponse(message="Document deleted.")
