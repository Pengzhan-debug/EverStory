"""API contracts expressed as a boundary/authorization/fault-injection matrix."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from everstory.pipeline import TurnPipeline
from everstory.storage import RuntimeConflict

pytestmark = pytest.mark.api
TEXT_ENDPOINTS = ["/api/turn", "/api/turn/stream", "/api/agents/chat"]


def world(client):
    response = client.get("/api/world")
    assert response.status_code == 200
    return response.json()


def sse_events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.mark.parametrize("endpoint", TEXT_ENDPOINTS)
@pytest.mark.parametrize("payload", [
    pytest.param({}, id="missing-text"),
    pytest.param({"text": None}, id="null-text"),
    pytest.param({"text": ""}, id="empty-text"),
    pytest.param({"text": " \t\n"}, id="whitespace-text"),
    pytest.param({"text": 42}, id="integer-text"),
    pytest.param({"text": True}, id="boolean-text"),
    pytest.param({"text": ["wait"]}, id="array-text"),
    pytest.param({"text": {"action": "wait"}}, id="object-text"),
])
def test_text_input_rejected_without_state_mutation(client, endpoint, payload):
    before = world(client)["state_hash"]
    conversation_before = client.get("/api/conversation").json()["messages"]
    team_before = client.get("/api/agents/chat").json()["messages"]
    response = client.post(endpoint, json=payload)
    assert response.status_code == 400, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]
    assert world(client)["state_hash"] == before
    assert client.get("/api/conversation").json()["messages"] == conversation_before
    assert client.get("/api/agents/chat").json()["messages"] == team_before


@pytest.mark.parametrize("endpoint", TEXT_ENDPOINTS)
@pytest.mark.parametrize("raw_body", [
    pytest.param(b'{"text":', id="truncated-json"),
    pytest.param(b'\xff', id="invalid-utf8"),
    pytest.param(b'[]', id="json-array"),
    pytest.param(b'null', id="json-null"),
    pytest.param(b'"wait"', id="json-string"),
])
def test_invalid_json_shape_returns_client_error(client, endpoint, raw_body):
    before = world(client)["state_hash"]
    response = client.post(endpoint, content=raw_body, headers={"Content-Type": "application/json"})
    assert response.status_code == 400, response.text
    assert response.json()["error"]
    assert world(client)["state_hash"] == before


@pytest.mark.parametrize("endpoint", TEXT_ENDPOINTS)
@pytest.mark.parametrize("token", [None, "wrong-token", "a" * 64], ids=["missing", "malformed", "foreign"])
def test_csrf_failures_do_not_mutate_state(client, endpoint, token):
    before = world(client)["state_hash"]
    del client.headers["X-CSRF-Token"]
    if token is not None:
        client.headers["X-CSRF-Token"] = token
    response = client.post(endpoint, json={"text": "move to dock"})
    assert response.status_code == 403
    assert world(client)["state_hash"] == before


@pytest.mark.parametrize("locale", ["en", "zh-CN"])
def test_valid_turn_matches_committed_world(client, locale):
    response = client.post("/api/turn", json={"text": "move to dock", "locale": locale})
    assert response.status_code == 200
    result = response.json()
    assert result["events"][0]["ok"] is True
    assert result["world"]["player"]["location_id"] == "dock"
    assert result["state_hash"] == world(client)["state_hash"]
    assert result["turn"] == world(client)["turn"] == 1


@pytest.mark.parametrize("text", ["move to cave", "take rusty key", "use flint on lantern"])
def test_invalid_business_actions_leave_authoritative_state_unchanged(client, text):
    before = world(client)["state_hash"]
    response = client.post("/api/turn", json={"text": text})
    assert response.status_code == 200  # Request valid; business action rejected.
    assert response.json()["events"]
    assert all(event["ok"] is False for event in response.json()["events"])
    assert world(client)["state_hash"] == before


def test_sse_done_matches_persisted_state(client):
    response = client.post("/api/turn/stream", json={"text": "move to dock"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response)
    assert events[-1]["type"] == "done"
    assert sum(event["type"] == "done" for event in events) == 1
    assert not any(event["type"] == "error" for event in events)
    assert world(client)["player"]["location_id"] == "dock"
    assert world(client)["turn"] == 1


def test_synchronous_timeout_returns_gateway_error_and_allows_recovery(client):
    original = TurnPipeline.process

    def timed_out(pipeline, *args, **kwargs):
        original(pipeline, *args, **kwargs)  # Mutate the in-memory state first.
        raise TimeoutError("simulated provider timeout")

    before = world(client)["state_hash"]
    with patch.object(TurnPipeline, "process", timed_out):
        response = client.post("/api/turn", json={"text": "move to dock"})
    assert response.status_code == 502, response.text
    assert response.json()["code"] == "model_timeout"
    assert world(client)["state_hash"] == before
    assert client.post("/api/turn", json={"text": "move to dock"}).status_code == 200
    assert world(client)["turn"] == 1


def test_stream_timeout_emits_error_without_done_or_commit(client):
    original = TurnPipeline.process_stream

    def interrupted(*args, **kwargs):
        yield from original(*args, **kwargs)
        raise TimeoutError("simulated provider timeout")

    before = world(client)["state_hash"]
    with patch.object(TurnPipeline, "process_stream", interrupted):
        response = client.post("/api/turn/stream", json={"text": "move to dock"})
    events = sse_events(response)
    assert any(event["type"] == "error" for event in events)
    assert not any(event["type"] == "done" for event in events)
    assert world(client)["state_hash"] == before


def test_commit_conflict_returns_409_and_restores_durable_state(client, app):
    before = world(client)["state_hash"]
    with patch.object(app.state.storage, "save_runtime", side_effect=RuntimeConflict("stale request")):
        response = client.post("/api/turn", json={"text": "move to dock"})
    assert response.status_code == 409
    assert response.json()["code"] == "runtime_conflict"
    assert world(client)["state_hash"] == before


def test_task_double_approval_does_not_execute_twice(client):
    proposed = client.post("/api/agents/chat", json={"text": "@field travel to Dock."})
    assert proposed.status_code == 200
    task = next(t for t in proposed.json()["tasks"] if t.get("action"))
    path = f"/api/agents/tasks/{task['id']}/approve"
    assert client.post(path).status_code == 200
    once = world(client)["state_hash"]
    assert client.post(path).status_code == 400
    assert world(client)["state_hash"] == once
    assert world(client)["turn"] == 1


def test_cross_user_save_cannot_be_loaded(client, app, authorize):
    saved = client.post("/api/save", json={"name": "owned-save"})
    assert saved.status_code == 200
    with TestClient(app, raise_server_exceptions=False) as outsider:
        authorize(outsider)
        before = world(outsider)["state_hash"]
        response = outsider.post("/api/load", json={"path": saved.json()["path"]})
        assert response.status_code == 400
        assert outsider.get("/api/saves").json()["saves"] == []
        assert world(outsider)["state_hash"] == before


def test_rate_limit_boundary_is_session_scoped(client, app, authorize):
    runtime = app.state.redis_runtime
    runtime.rate_limit, runtime.rate_window = 2, 86400
    assert client.post("/api/turn", json={"text": "wait"}).status_code == 200
    assert client.post("/api/turn", json={"text": "wait"}).status_code == 200
    response = client.post("/api/turn", json={"text": "wait"})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert world(client)["turn"] == 2
    with TestClient(app) as other:
        authorize(other)
        assert other.post("/api/turn", json={"text": "wait"}).status_code == 200
        assert world(other)["turn"] == 1


@pytest.mark.parametrize("path", ["/api/admin/overview", "/api/auth/investigations"])
def test_guest_cannot_read_account_or_admin_data(client, path):
    assert client.get(path).status_code == 403


def test_guest_can_list_own_device_session(client):
    response = client.get("/api/auth/sessions")
    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["current"] is True
