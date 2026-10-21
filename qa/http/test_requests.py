"""Real socket tests: cookies, CSRF, persistence, isolation and SSE framing."""

import json

import allure
import pytest
import requests

TIMEOUT = (3, 10)  # connect, read; no request is allowed to wait indefinitely
pytestmark = [allure.feature("Real HTTP / Requests")]


@pytest.fixture
def session(base_url):
    with requests.Session() as client:
        client.trust_env = False
        response = client.get(base_url + "/api/auth/session", timeout=TIMEOUT)
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = client.cookies["everstory_csrf"]
        yield client


def world(session, base_url):
    response = session.get(base_url + "/api/world", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def test_cookie_session_and_json_turn(session, base_url):
    assert {"everstory_auth", "everstory_runtime", "everstory_csrf"} <= set(session.cookies.keys())
    response = session.post(base_url + "/api/turn", json={"text": "move to dock"}, timeout=TIMEOUT)
    response.raise_for_status()
    result = response.json()
    committed = world(session, base_url)
    assert result["world"]["player"]["location_id"] == "dock"
    assert result["turn"] == committed["turn"] == 1
    assert result["state_hash"] == committed["state_hash"]


@pytest.mark.parametrize("header", [None, "wrong"])
def test_csrf_rejection_does_not_commit(session, base_url, header):
    before = world(session, base_url)
    session.headers.pop("X-CSRF-Token")
    if header:
        session.headers["X-CSRF-Token"] = header
    response = session.post(base_url + "/api/turn", json={"text": "wait"}, timeout=TIMEOUT)
    assert response.status_code == 403
    assert world(session, base_url)["state_hash"] == before["state_hash"]


def test_malformed_json_over_http(session, base_url):
    before = world(session, base_url)["state_hash"]
    response = session.post(base_url + "/api/turn", data=b'{"text":',
                            headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
    assert response.status_code == 400
    assert response.json()["error"]
    assert world(session, base_url)["state_hash"] == before


def test_stream_terminal_event_matches_durable_state(session, base_url):
    events = []
    with session.post(base_url + "/api/turn/stream", json={"text": "move to dock"},
                      stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        assert response.headers["content-type"].startswith("text/event-stream")
        # Small chunks exercise framing across TCP reads, rather than response.json().
        for line in response.iter_lines(chunk_size=17):
            if line.startswith(b"data: "):
                events.append(json.loads(line[6:]))
    allure.attach(json.dumps(events, ensure_ascii=False, indent=2), "SSE events", allure.attachment_type.JSON)
    assert events[-1]["type"] == "done"
    assert sum(event["type"] == "done" for event in events) == 1
    assert not any(event["type"] == "error" for event in events)
    committed = world(session, base_url)
    assert events[-1]["world"]["state_hash"] == committed["state_hash"]
    assert committed["turn"] == 1


def test_save_load_and_foreign_session_isolation(session, base_url):
    session.post(base_url + "/api/turn", json={"text": "move to dock"}, timeout=TIMEOUT).raise_for_status()
    saved_world = world(session, base_url)
    saved = session.post(base_url + "/api/save", json={"name": "http-qa"}, timeout=TIMEOUT)
    saved.raise_for_status()
    path = saved.json()["path"]
    session.post(base_url + "/api/turn", json={"text": "wait"}, timeout=TIMEOUT).raise_for_status()
    assert world(session, base_url)["turn"] == 2
    session.post(base_url + "/api/load", json={"path": path}, timeout=TIMEOUT).raise_for_status()
    assert world(session, base_url)["state_hash"] == saved_world["state_hash"]
    with requests.Session() as outsider:
        outsider.trust_env = False
        outsider.get(base_url + "/api/auth/session", timeout=TIMEOUT).raise_for_status()
        outsider.headers["X-CSRF-Token"] = outsider.cookies["everstory_csrf"]
        assert world(outsider, base_url)["turn"] == 0
        denied = outsider.post(base_url + "/api/load", json={"path": path}, timeout=TIMEOUT)
        assert denied.status_code == 400
        assert world(outsider, base_url)["turn"] == 0
