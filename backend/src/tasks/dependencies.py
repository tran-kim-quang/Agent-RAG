from dataclasses import dataclass
from functools import lru_cache

from backend.src.db import Database, SqlChatRepository, SqlDocumentRepository, SqlKnowledgeBaseRepository, SqlUploadRepository
from backend.src.services import TaskRecoveryService
from backend.src.storage import MinioObjectStorage
from backend.src.services.chat_service import ChatService
from backend.src.tasks.runners import ChatTaskRunner, UploadTaskRunner
from backend.src.tools.processData_tool import process_and_ingest_uploaded_file
from backend.src.infrastructure.token_stream import ChatTokenStreamPublisher


@dataclass(frozen=True)
class TaskDependencies:
    chat_runner: ChatTaskRunner
    upload_runner: UploadTaskRunner
    recovery: TaskRecoveryService


@lru_cache(maxsize=1)
def get_task_dependencies() -> TaskDependencies:
    database = Database()
    chats = SqlChatRepository(database)
    uploads = SqlUploadRepository(database)
    documents = SqlDocumentRepository(database)
    knowledge_bases = SqlKnowledgeBaseRepository(database)
    storage = MinioObjectStorage()
    return TaskDependencies(
        chat_runner=ChatTaskRunner(chats, ChatService(), ChatTokenStreamPublisher()),
        upload_runner=UploadTaskRunner(uploads, documents, storage, knowledge_bases, process_and_ingest_uploaded_file),
        recovery=TaskRecoveryService(chats, uploads),
    )
