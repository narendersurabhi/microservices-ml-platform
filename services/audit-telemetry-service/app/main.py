import asyncio
import os
import uuid
from datetime import datetime
from typing import List

import redis
from fastapi import Depends, FastAPI
from platform_lib.auth import require_role
from platform_lib.http_logging import HttpLoggingMiddleware
from platform_lib.logging import configure_logging
from platform_lib.request_id import RequestIdMiddleware
from platform_lib.tracing import configure_tracing, instrument_app
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session
from sqlmodel import Field, SQLModel, create_engine, select

configure_logging()
configure_tracing("audit-telemetry-service")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://audit:password@audit-db:5432/auditdb"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

engine = create_engine(DATABASE_URL)
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


class AuditEvent(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_type: str
    payload: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEventRead(SQLModel):
    id: uuid.UUID
    event_type: str
    payload: str
    created_at: datetime


app = FastAPI(
    title="Audit Telemetry Service", version="1.0.0", openapi_url="/v1/audit/openapi.json"
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpLoggingMiddleware)
instrument_app(app)
Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def on_startup() -> None:
    SQLModel.metadata.create_all(engine)
    asyncio.create_task(consume_events())


async def consume_events() -> None:
    stream = "case-events"
    group = "audit-consumers"
    consumer = "audit-service"
    try:
        redis_client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError:
        pass
    while True:
        entries = redis_client.xreadgroup(group, consumer, {stream: ">"}, count=10, block=2000)
        for _, messages in entries:
            for message_id, data in messages:
                with Session(engine) as session:
                    event = AuditEvent(
                        event_type=data.get("event_type"), payload=data.get("payload")
                    )
                    session.add(event)
                    session.commit()
                redis_client.xack(stream, group, message_id)
        await asyncio.sleep(0.1)


@app.get(
    "/v1/audit",
    response_model=List[AuditEventRead],
    dependencies=[Depends(require_role(["admin", "analyst"]))],
)
async def list_audit_events() -> List[AuditEventRead]:
    with Session(engine) as session:
        return [AuditEventRead.from_orm(event) for event in session.exec(select(AuditEvent)).all()]


@app.get("/v1/audit/health")
async def health() -> dict:
    return {"status": "ok"}
