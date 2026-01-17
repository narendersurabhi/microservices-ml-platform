import asyncio
import os
import random
import uuid
from datetime import datetime
from typing import Optional

import httpx
import redis
from fastapi import FastAPI, Header, HTTPException, Request
from platform_lib.auth import decode_jwt_token
from platform_lib.http_logging import HttpLoggingMiddleware
from platform_lib.logging import configure_logging
from platform_lib.request_id import RequestIdMiddleware
from platform_lib.tracing import configure_tracing, instrument_app
from prometheus_fastapi_instrumentator import Instrumentator

configure_logging()
configure_tracing("scoring-service")

CASE_SERVICE_URL = os.getenv("CASE_SERVICE_URL", "http://case-service:8000")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN")

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="Scoring Service", version="1.0.0", openapi_url="/v1/scoring/openapi.json")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpLoggingMiddleware)
instrument_app(app)
Instrumentator().instrument(app).expose(app)


def internal_or_jwt(
    request: Request, internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token")
) -> None:
    if internal_token and internal_token == os.getenv("INTERNAL_TOKEN", "internal-dev-token"):
        return
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing token")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        decode_jwt_token(token)
        return
    raise HTTPException(status_code=401, detail="Invalid token")


async def fetch_case(case_id: uuid.UUID) -> Optional[dict]:
    if not SERVICE_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
    async with httpx.AsyncClient(timeout=2.0) as client:
        response = await client.get(f"{CASE_SERVICE_URL}/v1/cases/{case_id}", headers=headers)
        if response.status_code != 200:
            return None
        return response.json()


async def fetch_user(user_id: uuid.UUID) -> Optional[dict]:
    if not SERVICE_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
    async with httpx.AsyncClient(timeout=2.0) as client:
        response = await client.get(f"{USER_SERVICE_URL}/v1/users/{user_id}", headers=headers)
        if response.status_code != 200:
            return None
        return response.json()


def emit_event(event_type: str, payload: dict) -> None:
    redis_client.xadd(
        "case-events",
        {"event_type": event_type, "payload": payload, "created_at": datetime.utcnow().isoformat()},
    )


@app.post("/v1/scoring/{case_id}")
async def score_case(
    case_id: uuid.UUID,
    request: Request,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
) -> dict:
    internal_or_jwt(request=request, internal_token=internal_token)
    await asyncio.sleep(random.uniform(0.3, 1.2))
    if random.random() < 0.2:
        raise HTTPException(status_code=503, detail="Scoring engine unavailable")
    case = await fetch_case(case_id)
    owner_id = case.get("owner_id") if case else None
    owner = await fetch_user(uuid.UUID(owner_id)) if owner_id else None
    score = round(random.uniform(0.1, 0.99), 4)
    payload = {
        "case_id": str(case_id),
        "score": score,
        "owner": owner,
        "idempotency_key": idempotency_key,
        "updated_at": datetime.utcnow().isoformat(),
    }
    emit_event("score_updated", payload)
    return {"case_id": case_id, "score": score, "updated_at": datetime.utcnow()}


@app.get("/v1/scoring/health")
async def health() -> dict:
    return {"status": "ok"}
