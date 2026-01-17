import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from platform_lib.http_logging import HttpLoggingMiddleware
from platform_lib.logging import configure_logging
from platform_lib.request_id import RequestIdMiddleware
from platform_lib.tracing import configure_tracing, instrument_app
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

configure_logging()
configure_tracing("auth-service")

app = FastAPI(title="Auth Service", version="1.0.0", openapi_url="/v1/auth/openapi.json")
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpLoggingMiddleware)
instrument_app(app)
Instrumentator().instrument(app).expose(app)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    role: str


FAKE_USERS = {
    "admin@example.com": {"password": "admin123", "role": "admin"},
    "analyst@example.com": {"password": "analyst123", "role": "analyst"},
    "viewer@example.com": {"password": "viewer123", "role": "viewer"},
}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = FAKE_USERS.get(username)
    if not user or user["password"] != password:
        return None
    return {"sub": username, "role": user["role"]}


@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {**user, "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_MINUTES * 60,
        role=user["role"],
    )


@app.get("/v1/auth/health")
async def health() -> dict:
    return {"status": "ok"}
