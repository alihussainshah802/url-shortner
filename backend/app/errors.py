import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.middleware import REQUEST_ID_HEADER

logger = logging.getLogger("app.errors")

# Failures that mean "the database can't be reached right now", as opposed to a bug.
DATABASE_UNAVAILABLE = (OperationalError, InterfaceError, PoolTimeoutError)


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_of(request)
    logger.error(
        "Database unavailable [request %s] %s %s: %s %s",
        request_id,
        request.method,
        request.url.path,
        type(exc).__name__,
        str(exc).splitlines()[0] if str(exc) else "",
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "The service is temporarily unavailable. Try again in a moment.",
            "request_id": request_id,
        },
        headers={"Retry-After": "5"},
    )


async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_of(request)
    logger.error(
        "Unhandled error [request %s] %s %s",
        request_id,
        request.method,
        request.url.path,
        exc_info=exc,
    )
    # This handler runs outside the request-id middleware, so set the header here.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Something went wrong on our side. Try again.",
            "request_id": request_id,
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    for error_type in DATABASE_UNAVAILABLE:
        app.add_exception_handler(error_type, database_unavailable)
    app.add_exception_handler(Exception, unhandled_error)
