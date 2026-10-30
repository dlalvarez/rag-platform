import pytest
from fastapi.testclient import TestClient

from rag_platform.api import create_app
from rag_platform.config import Settings


def test_v01_health_and_no_business_routes():
    client = TestClient(create_app(Settings()))
    assert client.get("/healthz").json() == {"status": "ok", "phase": "F00"}
    for path in ("/tenants", "/documents", "/chat", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_v01_bad_configuration_does_not_echo_value():
    secret_value = "synthetic-sensitive-value"
    with pytest.raises(ValueError, match="RAG_LOG_LEVEL is invalid") as error:
        Settings.from_env({"RAG_LOG_LEVEL": secret_value})
    assert secret_value not in str(error.value)


def test_v01_default_configuration():
    assert Settings.from_env({}).log_level == "info"
