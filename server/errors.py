"""Error types that carry a stable code and a user-facing Turkish message."""

from __future__ import annotations

from server.schemas import ErrorPayload


class UserFacingError(Exception):
    """An error whose message is safe to show in the UI."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def payload(self) -> ErrorPayload:
        return ErrorPayload(code=self.code, message=self.message)


class AdapterError(UserFacingError):
    """Raised by adapters for expected failures (missing API key, bad path...)."""


API_KEY_MISSING = "api_key_missing"
CANCELLED = "cancelled"
INTERNAL = "internal"

INTERNAL_MESSAGE = "Beklenmeyen bir hata oluştu. Ayrıntılar sunucu günlüğünde."
