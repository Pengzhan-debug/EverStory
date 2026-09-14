"""Opt-in tests against disposable PostgreSQL/Redis services, never production.

CI supplies TEST_DATABASE_URL and TEST_REDIS_URL. Offline unit tests skip these.
The test database must already have been migrated and include 'test' in its name.
"""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from everstory.api.main import create_app
from everstory.llm.client import LLMClient
from everstory.redis_runtime import RedisRuntime
from everstory.storage import DatabaseStorage, RuntimeConflict


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL") and os.getenv("TEST_REDIS_URL"), "Dedicated PostgreSQL/Redis test services not configured")
class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        url = os.environ["TEST_DATABASE_URL"]
        self.assertIn("test", make_url(url).database.lower(), "Use a disposable test database")
        self.storage = DatabaseStorage(url, create_schema=False)
        self.a_redis = RedisRuntime(os.environ["TEST_REDIS_URL"], strict=True)
        self.b_redis = RedisRuntime(os.environ["TEST_REDIS_URL"], strict=True)
        self.assertTrue(self.storage.health()["ok"])
        self.assertTrue(self.a_redis.health()["ok"])
        self.client_patch = patch("everstory.api.main.build_client", side_effect=lambda: LLMClient(mode="stub"))
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()
        self.a_redis._client.close()
        self.b_redis._client.close()
        self.storage.engine.dispose()

    def test_independent_workers_serialize_turns(self):
        with TestClient(create_app(self.storage, self.a_redis)) as a, TestClient(create_app(self.storage, self.b_redis)) as b:
            a.get("/api/world")
            a.headers["X-CSRF-Token"] = a.cookies.get("everstory_csrf")
            b.cookies.update(a.cookies)
            b.headers.update(a.headers)
            b.get("/api/world")
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda c: c.post("/api/turn", json={"text": "wait"}), [a, b]))
            self.assertEqual([r.status_code for r in responses], [200, 200])
            self.assertEqual(sorted(r.json()["turn"] for r in responses), [1, 2])
            self.assertEqual(a.get("/api/world").json()["turn"], 2)
            self.assertEqual(b.get("/api/world").json()["turn"], 2)

    def test_postgres_compare_and_swap_has_only_one_winner(self):
        user, runtime = uuid4().hex, uuid4().hex
        self.storage.save_runtime(user, runtime, {"version": "initial"}, expected_revision=0)
        def attempt(value):
            try:
                self.storage.save_runtime(user, runtime, {"value": value}, expected_revision=1)
                return "saved"
            except RuntimeConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ["a", "b"]))
        self.assertCountEqual(outcomes, ["saved", "conflict"])

    def test_lost_redis_lease_is_detected_before_commit(self):
        runtime = uuid4().hex
        # Delete only the random test lock, simulating expiry/replacement.
        with self.assertRaises(RuntimeError):
            with self.a_redis.session_lock(runtime) as assert_owned:
                self.b_redis._client.delete(f"everstory:lock:{runtime}")
                assert_owned()
