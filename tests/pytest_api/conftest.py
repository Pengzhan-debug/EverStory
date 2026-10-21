"""Isolated SQLite apps and deterministic model clients for API experiments."""

import pytest
from fastapi.testclient import TestClient

from everstory.api import main as api
from everstory.llm.client import LLMClient
from everstory.redis_runtime import RedisRuntime
from everstory.storage import DatabaseStorage


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "stub")
    monkeypatch.setenv("CSRF_ENFORCE", "true")
    monkeypatch.setenv("LIVE_LLM_REQUIRE_ACCOUNT", "true")
    monkeypatch.setattr(api, "build_client", lambda: LLMClient(mode="stub"))
    storage = DatabaseStorage(f"sqlite:///{(tmp_path / 'api-test.sqlite').as_posix()}")
    application = api.create_app(storage, RedisRuntime())
    yield application
    storage.engine.dispose()


def authorize_client(client):
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = client.cookies["everstory_csrf"]
    return client


@pytest.fixture
def authorize():
    return authorize_client


@pytest.fixture
def client(app, authorize):
    # Return 500 responses to the test, so an uncaught application exception is
    # measured as an HTTP contract failure rather than hidden by the test client.
    with TestClient(app, raise_server_exceptions=False) as browser:
        yield authorize(browser)
