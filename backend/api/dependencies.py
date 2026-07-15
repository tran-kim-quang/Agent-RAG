from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv

from backend.src.core.roles import is_admin
from backend.src.db import Database, SqlChatRepository, SqlDocumentRepository, SqlRefreshTokenRepository, SqlUploadRepository, SqlUserRepository, User
from backend.src.security import AuthService, TokenError
from backend.src.services import ChatRunService, GraphQueryService, UploadJobService
from backend.src.storage import MinioObjectStorage

load_dotenv()

database = Database()
users = SqlUserRepository(database)
tokens = SqlRefreshTokenRepository(database)
chats = SqlChatRepository(database)
uploads = SqlUploadRepository(database)
documents = SqlDocumentRepository(database)
auth_service = AuthService(users, tokens)
object_storage = MinioObjectStorage()
chat_runs = ChatRunService(chats)
graph_queries = GraphQueryService()
upload_jobs = UploadJobService(uploads, object_storage)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        return auth_service.decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin(user.role):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
