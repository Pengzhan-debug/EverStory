import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from everstory.api.main import SESSION_COOKIE, create_app
from everstory.engine import WorldSession
from everstory.llm.client import LLMClient
from everstory.persistence import session_to_dict
from everstory.redis_runtime import RedisRuntime
from everstory.storage import DatabaseStorage, normalize_database_url
from everstory.worlds import load_world


class DatabaseStorageTests(unittest.TestCase):
    def test_hosted_postgres_urls_use_psycopg3(self):
        self.assertEqual(
            normalize_database_url("postgresql://user:pass@db/app"),
            "postgresql+psycopg://user:pass@db/app",
        )
        self.assertEqual(
            normalize_database_url("postgres://user:pass@db/app"),
            "postgresql+psycopg://user:pass@db/app",
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "everstory-test.db"
        self.storage = DatabaseStorage(f"sqlite:///{db_path.as_posix()}")
        self.session_id = "a" * 32

    def tearDown(self):
        self.storage.engine.dispose()
        self.tmp.cleanup()

    def test_runtime_round_trip(self):
        world = WorldSession(load_world("lost_lighthouse"))
        payload = session_to_dict(world, extra={"pipeline": {"transcript": []}})
        self.storage.save_runtime(self.session_id, payload)

        restored = self.storage.load_runtime(self.session_id)

        self.assertEqual(restored["world"], "lost_lighthouse")
        self.assertEqual(restored["state"]["turn"], 0)

    def test_database_saves_are_isolated_by_session(self):
        world = WorldSession(load_world("lost_lighthouse"))
        reference = self.storage.save_game(
            self.session_id, "first clue", world, {"team_chat": {"evidence": []}}
        )

        self.assertTrue(reference.startswith("db:"))
        self.assertEqual(len(self.storage.list_games(self.session_id)), 1)
        restored, _ = self.storage.load_game(self.session_id, reference)
        self.assertEqual(restored.world_name, "lost_lighthouse")
        with self.assertRaises(ValueError):
            self.storage.load_game("b" * 32, reference)

    def test_usage_ledger_is_idempotent(self):
        event = {
            "id": "c" * 32,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent": "skeptic",
            "model": "test-model",
            "total_tokens": 42,
        }
        self.storage.sync_usage(self.session_id, [event])
        self.storage.sync_usage(self.session_id, [event])

        calls = self.storage.load_usage(self.session_id)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["total_tokens"], 42)

    def test_api_runtime_survives_app_restart(self):
        coordinator = RedisRuntime(rate_limit=0)
        with patch(
            "everstory.api.main.build_client", side_effect=lambda: LLMClient(mode="stub")
        ):
            first_app = create_app(self.storage, coordinator)
            with TestClient(first_app) as first_client:
                response = first_client.post(
                    "/api/turn", json={"text": "look", "locale": "en"}
                )
                self.assertEqual(response.status_code, 200)
                turn = response.json()["world"]["turn"]
                session_cookie = first_client.cookies.get(SESSION_COOKIE)

            second_app = create_app(self.storage, RedisRuntime(rate_limit=0))
            with TestClient(second_app) as second_client:
                second_client.cookies.set(SESSION_COOKIE, session_cookie)
                restored = second_client.get("/api/world")

        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["turn"], turn)


class RedisRuntimeTests(unittest.TestCase):
    def test_local_rate_limit_fallback(self):
        runtime = RedisRuntime(rate_limit=2, rate_window=60)

        self.assertEqual(runtime.allow("player"), (True, 1))
        self.assertEqual(runtime.allow("player"), (True, 0))
        self.assertEqual(runtime.allow("player"), (False, 0))

    def test_memory_session_lock_is_reentrant(self):
        runtime = RedisRuntime()
        with runtime.session_lock("player"):
            with runtime.session_lock("player"):
                pass


if __name__ == "__main__":
    unittest.main()
