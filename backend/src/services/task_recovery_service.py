from datetime import datetime, timedelta, timezone

from backend.src.core.repositories import ChatRepository, UploadRepository


class TaskRecoveryService:
    def __init__(self, chats: ChatRepository, uploads: UploadRepository) -> None:
        self.chats = chats
        self.uploads = uploads

    def fail_stale_tasks(self, stale_minutes: int) -> tuple[int, int]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=stale_minutes)
        return self.uploads.fail_stale(cutoff, now), self.chats.fail_stale(cutoff, now)
