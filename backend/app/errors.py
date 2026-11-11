"""One error shape for every failure: {"error": {"code", "message", "details"}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("adal")

_HTTP_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    429: "rate_limited",
}

# PostgreSQL: lock_not_available, query_canceled (statement_timeout).
_BUSY_SQLSTATES = {"55P03", "57014"}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def not_found(message: str = "Not found.") -> ApiError:
    return ApiError(404, "not_found", message)


def forbidden(message: str = "You do not have access to this.") -> ApiError:
    return ApiError(403, "forbidden", message)


def field_error(field: str, message: str) -> ApiError:
    return ApiError(422, "validation_error", "Some fields need attention.", {"fields": {field: message}})


def _sqlstate(exc: DBAPIError) -> str | None:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(getattr(orig, "__cause__", None), "sqlstate", None)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path", "header")]
            fields.setdefault(".".join(loc) or "request", str(err.get("msg", "Invalid value.")))
        return JSONResponse(error_body("validation_error", "Some fields need attention.", {"fields": fields}), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(error_body(_HTTP_CODES.get(exc.status_code, "error"), message), status_code=exc.status_code)

    @app.exception_handler(DBAPIError)
    async def _db(_: Request, exc: DBAPIError) -> JSONResponse:
        if _sqlstate(exc) in _BUSY_SQLSTATES:
            return JSONResponse(
                error_body("busy", "The auction is busy right now. Try again."),
                status_code=503,
                headers={"Retry-After": "1"},
            )
        logger.exception("database error")
        return JSONResponse(error_body("internal_error", "Something went wrong on our side."), status_code=500)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(error_body("internal_error", "Something went wrong on our side."), status_code=500)
