import logging
from typing import Callable

from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class HttpLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        logger = logging.getLogger("http")
        request_id = getattr(request.state, "request_id", None)
        trace_id = trace.get_current_span().get_span_context().trace_id
        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
            },
        )
        response = await call_next(request)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "trace_id": trace_id,
                "status_code": response.status_code,
            },
        )
        return response
