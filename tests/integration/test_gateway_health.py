import time

import httpx
import pytest


@pytest.mark.integration
def test_gateway_health() -> None:
    time.sleep(5)
    response = httpx.get("http://localhost:8080/health", timeout=5.0)
    assert response.status_code == 200
