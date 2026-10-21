"""Mixed read/write load with per-user state assertions, against the QA server only."""

from urllib.parse import urlsplit

from locust import HttpUser, between, task
from locust.exception import StopUser


class Investigator(HttpUser):
    wait_time = between(0.1, 0.3)

    def on_start(self):
        if urlsplit(self.host).hostname not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("This experiment accepts loopback QA servers only")
        self.client.trust_env = False
        with self.client.get("/api/auth/session", name="GET auth (setup)",
                             timeout=(3, 10), catch_response=True) as response:
            if response.status_code != 200 or response.headers.get("X-EverStory-QA") != "stub-sqlite-memory":
                response.failure("Expected the disposable stub QA server")
                raise StopUser()
        self.client.headers["X-CSRF-Token"] = self.client.cookies["everstory_csrf"]
        self.turn = 0
        self.state_hash = None

    @task(3)
    def read_world(self):
        with self.client.get("/api/world", name="GET world", timeout=(3, 10), catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                data = response.json()
                assert data["turn"] == self.turn
                assert data["player"]["location_id"] == "storm_shore"
                if self.state_hash:
                    assert data["state_hash"] == self.state_hash
            except (ValueError, KeyError, AssertionError):
                response.failure("semantic: wrong turn/location/hash for this session")

    @task(1)
    def advance_world(self):
        with self.client.post("/api/turn", name="POST wait", json={"text": "wait"},
                              timeout=(3, 10), catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                raise StopUser()  # A failed write has an ambiguous commit outcome; do not cascade failures.
            try:
                data = response.json()
                assert data["turn"] == self.turn + 1
                assert data["world"]["turn"] == data["turn"]
                assert data["state_hash"] == data["world"]["state_hash"]
                assert data["world"]["player"]["location_id"] == "storm_shore"
                self.turn = data["turn"]
                self.state_hash = data["state_hash"]
            except (ValueError, KeyError, AssertionError):
                response.failure("semantic: lost/foreign turn or inconsistent state")
                raise StopUser()
