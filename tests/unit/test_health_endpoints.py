import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-secret")

from fastapi.testclient import TestClient

from langbridge.apps.api.langbridge_api.main import app as api_app
from langbridge.apps.gateway.langbridge_gateway.main import app as gateway_app


def test_api_health() -> None:
    client = TestClient(api_app)
    response = client.get("/api/v1/auth/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_gateway_health() -> None:
    client = TestClient(gateway_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
