from backend.src.tasks.retry_policy import is_retryable_task_error


class HttpError(RuntimeError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def test_retry_policy_only_retries_transient_failures() -> None:
    assert is_retryable_task_error(TimeoutError("timed out")) is True
    assert is_retryable_task_error(HttpError("service unavailable", 503)) is True
    assert is_retryable_task_error(HttpError("short rate limit", 429)) is True
    assert is_retryable_task_error(HttpError("weekly usage limit", 429)) is False
    assert is_retryable_task_error(ValueError("input length exceeds the context length")) is False
