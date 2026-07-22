from __future__ import annotations


_RETRYABLE_STATUS_CODES = {408, 425, 429, 502, 503, 504}
_NON_RETRYABLE_RATE_LIMIT_MARKERS = ("weekly usage limit", "quota")


def is_retryable_task_error(error: Exception) -> bool:
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True

    status_code = getattr(error, "status_code", None)
    response = getattr(error, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    if status_code not in _RETRYABLE_STATUS_CODES:
        return False
    if status_code == 429:
        message = str(error).lower()
        return not any(marker in message for marker in _NON_RETRYABLE_RATE_LIMIT_MARKERS)
    return True
