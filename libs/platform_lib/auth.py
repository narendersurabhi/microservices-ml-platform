import os
from typing import Callable, Dict, List

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt


def decode_jwt_token(token: str) -> Dict:
    secret = os.getenv("JWT_SECRET", "dev-secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


def require_role(allowed_roles: List[str]) -> Callable:
    async def _dependency(request: Request) -> Dict:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
        token = auth_header.split(" ", 1)[1]
        payload = decode_jwt_token(token)
        role = payload.get("role")
        if role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return payload

    return _dependency
