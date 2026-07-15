from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from minio import Minio
from minio.error import S3Error


class MinioObjectStorage:
    def __init__(self) -> None:
        self.bucket = os.getenv("MINIO_BUCKET", "agent-rag")
        self.client = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ROOT_USER", "agent-rag"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "change-me-in-production"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )

    def ensure_bucket(self) -> None:
        if self.client.bucket_exists(self.bucket):
            return
        try:
            self.client.make_bucket(self.bucket)
        except S3Error as exc:
            if exc.code not in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                raise

    def put_bytes(self, object_key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        self.ensure_bucket()
        self.client.put_object(
            self.bucket,
            object_key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        return object_key

    def get_bytes(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def put_path(self, object_key: str, path: str, content_type: str = "application/octet-stream") -> str:
        payload = Path(path).read_bytes()
        return self.put_bytes(object_key, payload, content_type)

    def presigned_download_url(self, object_key: str) -> str:
        return self.client.presigned_get_object(self.bucket, object_key)

    def object_uri(self, object_key: str) -> str:
        return f"s3://{self.bucket}/{object_key}"
