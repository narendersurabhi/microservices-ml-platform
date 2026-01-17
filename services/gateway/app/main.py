import os
from typing import Dict

import httpx
from fastapi import FastAPI, Request, Response
from platform_lib.auth import decode_jwt_token
from platform_lib.http_logging import HttpLoggingMiddleware
from platform_lib.logging import configure_logging
from platform_lib.request_id import RequestIdMiddleware
from platform_lib.tracing import configure_tracing, instrument_app
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

configure_logging()
configure_tracing("gateway")

SERVICE_URLS: Dict[str, str] = {
    "/v1/auth": os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000"),
    "/v1/users": os.getenv("USER_SERVICE_URL", "http://user-service:8000"),
    "/v1/cases": os.getenv("CASE_SERVICE_URL", "http://case-service:8000"),
    "/v1/scoring": os.getenv("SCORING_SERVICE_URL", "http://scoring-service:8000"),
    "/v1/audit": os.getenv("AUDIT_SERVICE_URL", "http://audit-telemetry-service:8000"),
}

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="Edge Gateway", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, limiter._rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpLoggingMiddleware)
instrument_app(app)
Instrumentator().instrument(app).expose(app)


async def _proxy(request: Request, upstream_base: str) -> Response:
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{upstream_base}{request.url.path}"
        headers = dict(request.headers)
        headers.pop("host", None)
        if "x-request-id" not in {k.lower() for k in headers}:
            headers["X-Request-Id"] = request.state.request_id
        body = await request.body()
        upstream_response = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
            params=request.query_params,
        )
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers={
            k: v for k, v in upstream_response.headers.items() if k.lower() != "content-encoding"
        },
    )


def _requires_auth(path: str) -> bool:
    if path.startswith("/v1/auth/login"):
        return False
    return any(path.startswith(prefix) for prefix in SERVICE_URLS)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if _requires_auth(request.url.path):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(status_code=401, content="Missing token")
        token = auth_header.split(" ", 1)[1]
        decode_jwt_token(token)
    return await call_next(request)


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@limiter.limit("30/minute")
async def gateway_proxy(path: str, request: Request) -> Response:
    for prefix, target in SERVICE_URLS.items():
        if request.url.path.startswith(prefix):
            return await _proxy(request, target)
    return Response(status_code=404, content="Route not found")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
