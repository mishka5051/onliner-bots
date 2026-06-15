from typing import Any


class AppError(Exception):
    """Base application error."""

    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"
    details: dict[str, Any]

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    message = "Validation failed"


class SearchQueryNotFoundError(AppError):
    code = "SEARCH_QUERY_NOT_FOUND"
    message = "Search query not found"


class SearchQueryInUseError(AppError):
    code = "SEARCH_QUERY_IN_USE"
    message = "Cannot delete search query that was used in a search run"


class SearchRunNotFoundError(AppError):
    code = "SEARCH_RUN_NOT_FOUND"
    message = "Search run not found"


class EventNotFoundError(AppError):
    code = "EVENT_NOT_FOUND"
    message = "Event candidate not found"


class InvalidEventStatusError(AppError):
    code = "INVALID_EVENT_STATUS"
    message = "Invalid event relevance status"


class SearchProviderError(AppError):
    code = "SEARCH_PROVIDER_ERROR"
    message = "Search provider request failed"


class SearchApiKeyMissingError(AppError):
    code = "SEARCH_API_KEY_MISSING"
    message = "Search API key is not configured"


class SearchApiUnavailableError(AppError):
    code = "SEARCH_API_UNAVAILABLE"
    message = "Search API is unavailable"
