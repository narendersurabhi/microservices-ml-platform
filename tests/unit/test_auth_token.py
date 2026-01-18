import os
from datetime import datetime, timedelta

import pytest

from libs.platform_lib.auth import decode_jwt_token

jose = pytest.importorskip("jose")
jwt = jose.jwt


def test_decode_jwt_token() -> None:
    os.environ["JWT_SECRET"] = "test-secret"
    token = jwt.encode(
        {"sub": "user", "role": "admin", "exp": datetime.utcnow() + timedelta(minutes=5)},
        "test-secret",
        algorithm="HS256",
    )
    payload = decode_jwt_token(token)
    assert payload["sub"] == "user"
    assert payload["role"] == "admin"
