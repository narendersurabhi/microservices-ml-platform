import asyncio
import os
import uuid
from datetime import datetime
from typing import List, Optional

import httpx
import pybreaker
import redis
from fastapi import Depends, FastAPI, Header, HTTPException
from platform_lib.auth import require_role
from platform_lib.http_logging import HttpLoggingMiddleware
from platform_lib.logging import configure_logging
from platform_lib.request_id import RequestIdMiddleware
from platform_lib.tracing import configure_tracing, instrument_app
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.orm import Session
from sqlmodel import Field, SQLModel, create_engine, select
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

configure_logging()
configure_tracing("case-service")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://case:password@case-db:5432/casedb")
SCORING_URL = os.getenv("SCORING_SERVICE_URL", "http://scoring-service:8000")
SCORING_SERVICE_TOKEN = os.getenv("SCORING_SERVICE_TOKEN")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "internal-dev-token")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

engine = create_engine(DATABASE_URL)
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30)
bulkhead = asyncio.Semaphore(5)


class IdempotencyKey(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("key"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(sa_column=Column(String, unique=True, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Case(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    status: str = "NEW"
    owner_id: uuid.UUID
    score: Optional[float] = None
    priority: str = "medium"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CaseCreate(SQLModel):
    title: str
    owner_id: uuid.UUID
    priority: Optional[str] = "medium"


class CaseReadV1(SQLModel):
    id: uuid.UUID
    title: str
    status: str
    owner_id: uuid.UUID
    score: Optional[float]
    created_at: datetime


class CaseReadV2(CaseReadV1):
    priority: str


class ScoreResponse(SQLModel):
    case_id: uuid.UUID
    score: float


app = FastAPI(title="Case Service", version="2.0.0", openapi_url="/v1/cases/openapi.json")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpLoggingMiddleware)
instrument_app(app)
Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
def on_startup() -> None:
    SQLModel.metadata.create_all(engine)


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=5))
async def call_scoring(case_id: uuid.UUID) -> ScoreResponse:
    async with bulkhead:
        async with httpx.AsyncClient(timeout=3.0) as client:
            headers = {}
            if SCORING_SERVICE_TOKEN:
                headers["Authorization"] = f"Bearer {SCORING_SERVICE_TOKEN}"
            else:
                headers["X-Internal-Token"] = INTERNAL_TOKEN
            response = await client.post(f"{SCORING_URL}/v1/scoring/{case_id}", headers=headers)
            response.raise_for_status()
            data = response.json()
            return ScoreResponse(**data)


def emit_event(event_type: str, payload: dict) -> None:
    redis_client.xadd(
        "case-events",
        {"event_type": event_type, "payload": payload, "created_at": datetime.utcnow().isoformat()},
    )


def store_idempotency_key(session: Session, key: str) -> None:
    record = IdempotencyKey(key=key)
    session.add(record)


@app.post(
    "/v1/cases",
    response_model=CaseReadV1,
    dependencies=[Depends(require_role(["admin", "analyst"]))],
)
async def create_case(
    payload: CaseCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> CaseReadV1:
    with Session(engine) as session:
        if idempotency_key:
            existing = session.exec(
                select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="Duplicate idempotency key")
            store_idempotency_key(session, idempotency_key)
        case = Case(
            title=payload.title, owner_id=payload.owner_id, priority=payload.priority or "medium"
        )
        session.add(case)
        session.commit()
        session.refresh(case)
        emit_event("case_created", {"case_id": str(case.id), "owner_id": str(case.owner_id)})
    try:
        score_response = await breaker.call(call_scoring, case.id)
        with Session(engine) as session:
            stored = session.get(Case, case.id)
            if stored:
                stored.status = "SCORED"
                stored.score = score_response.score
                session.add(stored)
                session.commit()
        emit_event("score_updated", {"case_id": str(case.id), "score": score_response.score})
    except Exception:
        with Session(engine) as session:
            stored = session.get(Case, case.id)
            if stored:
                stored.status = "PENDING_SCORE"
                session.add(stored)
                session.commit()
        emit_event("score_pending", {"case_id": str(case.id)})
    return CaseReadV1(
        id=case.id,
        title=case.title,
        status=case.status,
        owner_id=case.owner_id,
        score=case.score,
        created_at=case.created_at,
    )


@app.get(
    "/v1/cases",
    response_model=List[CaseReadV1],
    dependencies=[Depends(require_role(["admin", "analyst", "viewer"]))],
)
async def list_cases() -> List[CaseReadV1]:
    with Session(engine) as session:
        return [
            CaseReadV1(
                id=case.id,
                title=case.title,
                status=case.status,
                owner_id=case.owner_id,
                score=case.score,
                created_at=case.created_at,
            )
            for case in session.exec(select(Case)).all()
        ]


@app.get(
    "/v1/cases/{case_id}",
    response_model=CaseReadV1,
    dependencies=[Depends(require_role(["admin", "analyst", "viewer"]))],
)
async def get_case(case_id: uuid.UUID) -> CaseReadV1:
    with Session(engine) as session:
        case = session.get(Case, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return CaseReadV1(
            id=case.id,
            title=case.title,
            status=case.status,
            owner_id=case.owner_id,
            score=case.score,
            created_at=case.created_at,
        )


@app.get(
    "/v2/cases",
    response_model=List[CaseReadV2],
    dependencies=[Depends(require_role(["admin", "analyst", "viewer"]))],
)
async def list_cases_v2() -> List[CaseReadV2]:
    with Session(engine) as session:
        return [
            CaseReadV2(
                id=case.id,
                title=case.title,
                status=case.status,
                owner_id=case.owner_id,
                score=case.score,
                created_at=case.created_at,
                priority=case.priority,
            )
            for case in session.exec(select(Case)).all()
        ]


@app.get("/v1/cases/health")
async def health() -> dict:
    return {"status": "ok"}
