from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError

STATUS_CODE_MAP: dict[str, int] = {
    "VALIDATION_ERROR": 400,
    "SEARCH_QUERY_NOT_FOUND": 404,
    "SEARCH_QUERY_IN_USE": 409,
    "SEARCH_RUN_NOT_FOUND": 404,
    "EVENT_NOT_FOUND": 404,
    "INVALID_EVENT_STATUS": 400,
    "SEARCH_PROVIDER_ERROR": 502,
    "SEARCH_API_KEY_MISSING": 503,
    "SEARCH_API_UNAVAILABLE": 503,
    "INTERNAL_ERROR": 500,
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        status_code = STATUS_CODE_MAP.get(exc.code, 500)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {"reason": str(exc)},
                }
            },
        )
