import os
import uuid
from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from platform_lib.auth import require_role
from platform_lib.http_logging import HttpLoggingMiddleware
from platform_lib.logging import configure_logging
from platform_lib.request_id import RequestIdMiddleware
from platform_lib.tracing import configure_tracing, instrument_app
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session
from sqlmodel import Field, SQLModel, create_engine, select

configure_logging()
configure_tracing("user-service")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://user:password@user-db:5432/userdb")
engine = create_engine(DATABASE_URL)


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str
    role: str
    full_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(SQLModel):
    email: str
    role: str
    full_name: str


class UserRead(SQLModel):
    id: uuid.UUID
    email: str
    role: str
    full_name: str
    created_at: datetime


app = FastAPI(title="User Service", version="1.0.0", openapi_url="/v1/users/openapi.json")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpLoggingMiddleware)
instrument_app(app)
Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
def on_startup() -> None:
    SQLModel.metadata.create_all(engine)


@app.post("/v1/users", response_model=UserRead, dependencies=[Depends(require_role(["admin"]))])
def create_user(payload: UserCreate) -> UserRead:
    with Session(engine) as session:
        user = User(email=payload.email, role=payload.role, full_name=payload.full_name)
        session.add(user)
        session.commit()
        session.refresh(user)
        return UserRead.from_orm(user)


@app.get(
    "/v1/users",
    response_model=List[UserRead],
    dependencies=[Depends(require_role(["admin", "analyst"]))],
)
def list_users() -> List[UserRead]:
    with Session(engine) as session:
        return [UserRead.from_orm(user) for user in session.exec(select(User)).all()]


@app.get(
    "/v1/users/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_role(["admin", "analyst", "viewer"]))],
)
def get_user(user_id: uuid.UUID) -> UserRead:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserRead.from_orm(user)


@app.get("/v1/users/health")
def health() -> dict:
    return {"status": "ok"}
