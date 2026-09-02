import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from everstory.api.main import AUTH_COOKIE, CSRF_COOKIE, SESSION_COOKIE, create_app
from everstory.engine import WorldSession
from everstory.llm.client import LLMClient
from everstory.persistence import session_to_dict
from everstory.redis_runtime import RedisRuntime
from everstory.storage import (
    AuthSession,
    DatabaseStorage,
    LoginChallenge,
    PlayerSession,
    User,
    normalize_database_url,
)
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
        self.user_id = "d" * 32
        self.session_id = "a" * 32

    def tearDown(self):
        self.storage.engine.dispose()
        self.tmp.cleanup()

    def test_runtime_round_trip(self):
        world = WorldSession(load_world("lost_lighthouse"))
        payload = session_to_dict(world, extra={"pipeline": {"transcript": []}})
        self.storage.save_runtime(self.user_id, self.session_id, payload)

        restored = self.storage.load_runtime(self.user_id, self.session_id)

        self.assertEqual(restored["world"], "lost_lighthouse")
        self.assertEqual(restored["state"]["turn"], 0)

    def test_guest_auth_token_is_hashed_and_identity_is_stable(self):
        token = "f" * 64
        first = self.storage.resolve_identity(token, self.session_id)
        second = self.storage.resolve_identity(
            first.replacement_auth_token, self.session_id
        )

        self.assertEqual(first.user_id, second.user_id)
        self.assertEqual(first.runtime_id, self.session_id)
        self.assertNotEqual(first.replacement_auth_token, token)
        self.assertEqual(second.replacement_auth_token, "")
        with Session(self.storage.engine) as db:
            auth = db.query(AuthSession).one()
            self.assertNotEqual(auth.token_hash, token)
            self.assertEqual(len(auth.token_hash), 64)

    def test_runtime_cannot_be_claimed_by_another_guest(self):
        first = self.storage.resolve_identity("1" * 64, self.session_id)
        second = self.storage.resolve_identity("2" * 64, self.session_id)

        self.assertNotEqual(first.user_id, second.user_id)
        self.assertNotEqual(second.runtime_id, self.session_id)
        self.assertTrue(second.runtime_replaced)

    def test_expired_auth_token_rotates_without_reclaiming_old_runtime(self):
        first = self.storage.resolve_identity("3" * 64, self.session_id)
        issued_token = first.replacement_auth_token
        with Session(self.storage.engine) as db, db.begin():
            auth = db.query(AuthSession).one()
            auth.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        replacement = self.storage.resolve_identity(issued_token, self.session_id)

        self.assertEqual(len(replacement.replacement_auth_token), 64)
        self.assertNotEqual(replacement.user_id, first.user_id)
        self.assertNotEqual(replacement.runtime_id, first.runtime_id)

    def test_legacy_session_is_adopted_by_first_auth_cookie(self):
        legacy = "9" * 32
        with Session(self.storage.engine) as db, db.begin():
            db.add(User(id=legacy, kind="guest"))
            db.add(PlayerSession(id=legacy, user_id=legacy))

        identity = self.storage.resolve_identity("4" * 64, legacy, legacy)

        self.assertEqual(identity.user_id, legacy)
        self.assertEqual(identity.runtime_id, legacy)

    def test_storage_queries_require_matching_user(self):
        world = WorldSession(load_world("lost_lighthouse"))
        payload = session_to_dict(world)
        self.storage.save_runtime(self.user_id, self.session_id, payload)

        self.assertIsNone(self.storage.load_runtime("e" * 32, self.session_id))
        with self.assertRaises(PermissionError):
            self.storage.save_runtime("e" * 32, self.session_id, payload)

    def test_email_verification_upgrades_guest_and_rotates_session(self):
        guest = self.storage.resolve_identity("5" * 64, self.session_id)
        challenge = self.storage.create_login_challenge(
            "Investigator@Example.com", "en"
        )

        registered = self.storage.verify_login_challenge(
            challenge["id"],
            "investigator@example.com",
            challenge["code"],
            guest.user_id,
            guest.auth_session_id,
            guest.runtime_id,
        )

        self.assertEqual(registered.user_id, guest.user_id)
        self.assertEqual(registered.runtime_id, guest.runtime_id)
        self.assertEqual(registered.kind, "registered")
        self.assertEqual(registered.email, "investigator@example.com")
        self.assertEqual(len(registered.replacement_auth_token), 64)
        self.assertEqual(len(registered.replacement_csrf_token), 64)
        with Session(self.storage.engine) as db:
            old_auth = db.get(AuthSession, guest.auth_session_id)
            user = db.get(User, guest.user_id)
            self.assertIsNotNone(old_auth.revoked_at)
            self.assertEqual(user.kind, "registered")

    def test_existing_account_login_merges_guest_runtime(self):
        first_runtime = "1" * 32
        account_guest = self.storage.resolve_identity("6" * 64, first_runtime)
        account_challenge = self.storage.create_login_challenge(
            "owner@example.com"
        )
        account = self.storage.verify_login_challenge(
            account_challenge["id"],
            "owner@example.com",
            account_challenge["code"],
            account_guest.user_id,
            account_guest.auth_session_id,
            first_runtime,
        )

        second_runtime = "2" * 32
        visitor = self.storage.resolve_identity("7" * 64, second_runtime)
        world = WorldSession(load_world("lost_lighthouse"))
        payload = session_to_dict(world)
        self.storage.save_runtime(visitor.user_id, second_runtime, payload)
        login_challenge = self.storage.create_login_challenge("owner@example.com")
        merged = self.storage.verify_login_challenge(
            login_challenge["id"],
            "owner@example.com",
            login_challenge["code"],
            visitor.user_id,
            visitor.auth_session_id,
            second_runtime,
        )

        self.assertEqual(merged.user_id, account.user_id)
        self.assertEqual(merged.runtime_id, second_runtime)
        self.assertIsNotNone(
            self.storage.load_runtime(account.user_id, second_runtime)
        )
        self.assertIsNone(
            self.storage.load_runtime(visitor.user_id, second_runtime)
        )

    def test_login_challenge_stores_hashes_and_is_single_use(self):
        guest = self.storage.resolve_identity("8" * 64, "8" * 32)
        challenge = self.storage.create_login_challenge("private@example.com")
        with Session(self.storage.engine) as db:
            row = db.get(LoginChallenge, challenge["id"])
            self.assertNotEqual(row.email_hash, "private@example.com")
            self.assertNotEqual(row.code_hash, challenge["code"])

        self.storage.verify_login_challenge(
            challenge["id"],
            "private@example.com",
            challenge["code"],
            guest.user_id,
            guest.auth_session_id,
            guest.runtime_id,
        )
        with self.assertRaises(ValueError):
            self.storage.verify_login_challenge(
                challenge["id"],
                "private@example.com",
                challenge["code"],
                guest.user_id,
                guest.auth_session_id,
                guest.runtime_id,
            )

    def test_login_challenge_persists_failed_attempt_limit(self):
        guest = self.storage.resolve_identity("9" * 64, "9" * 32)
        challenge = self.storage.create_login_challenge("limited@example.com")

        for _ in range(5):
            with self.assertRaises(ValueError):
                self.storage.verify_login_challenge(
                    challenge["id"],
                    "limited@example.com",
                    "000000" if challenge["code"] != "000000" else "000001",
                    guest.user_id,
                    guest.auth_session_id,
                    guest.runtime_id,
                )

        with Session(self.storage.engine) as db:
            row = db.get(LoginChallenge, challenge["id"])
            self.assertEqual(row.attempts, 5)
            self.assertIsNone(row.consumed_at)

        with self.assertRaises(ValueError):
            self.storage.verify_login_challenge(
                challenge["id"],
                "limited@example.com",
                challenge["code"],
                guest.user_id,
                guest.auth_session_id,
                guest.runtime_id,
            )

    def test_database_saves_are_isolated_by_session(self):
        world = WorldSession(load_world("lost_lighthouse"))
        reference = self.storage.save_game(
            self.user_id,
            self.session_id,
            "first clue",
            world,
            {"team_chat": {"evidence": []}},
        )

        self.assertTrue(reference.startswith("db:"))
        self.assertEqual(len(self.storage.list_games(self.user_id, self.session_id)), 1)
        restored, _ = self.storage.load_game(
            self.user_id, self.session_id, reference
        )
        self.assertEqual(restored.world_name, "lost_lighthouse")
        with self.assertRaises(ValueError):
            self.storage.load_game("e" * 32, self.session_id, reference)

    def test_usage_ledger_is_idempotent(self):
        event = {
            "id": "c" * 32,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent": "skeptic",
            "model": "test-model",
            "total_tokens": 42,
        }
        self.storage.sync_usage(self.user_id, self.session_id, [event])
        self.storage.sync_usage(self.user_id, self.session_id, [event])

        calls = self.storage.load_usage(self.user_id, self.session_id)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["total_tokens"], 42)

    def test_api_runtime_survives_app_restart(self):
        coordinator = RedisRuntime(rate_limit=0)
        with patch(
            "everstory.api.main.build_client", side_effect=lambda: LLMClient(mode="stub")
        ):
            first_app = create_app(self.storage, coordinator)
            with TestClient(first_app) as first_client:
                first_client.get("/api/auth/session")
                first_client.headers.update(
                    {"X-CSRF-Token": first_client.cookies.get(CSRF_COOKIE)}
                )
                response = first_client.post(
                    "/api/turn", json={"text": "look", "locale": "en"}
                )
                self.assertEqual(response.status_code, 200)
                turn = response.json()["world"]["turn"]
                session_cookie = first_client.cookies.get(SESSION_COOKIE)
                auth_cookie = first_client.cookies.get(AUTH_COOKIE)

            second_app = create_app(self.storage, RedisRuntime(rate_limit=0))
            with TestClient(second_app) as second_client:
                second_client.cookies.set(SESSION_COOKIE, session_cookie)
                second_client.cookies.set(AUTH_COOKIE, auth_cookie)
                restored = second_client.get("/api/world")

        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["turn"], turn)

    def test_health_and_static_assets_do_not_create_guest_rows(self):
        app = create_app(self.storage, RedisRuntime(rate_limit=0))
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").status_code, 200)
            self.assertEqual(client.get("/static/i18n.js").status_code, 200)

        with Session(self.storage.engine) as db:
            self.assertEqual(db.query(User).count(), 0)
            self.assertEqual(db.query(AuthSession).count(), 0)

    def test_alembic_upgrades_empty_database_to_identity_schema(self):
        migration_path = Path(self.tmp.name) / "migration-test.db"
        config = Config("alembic.ini")
        url = f"sqlite:///{migration_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", url)

        command.upgrade(config, "head")

        engine = create_engine(url)
        try:
            schema = inspect(engine)
            self.assertIn("auth_sessions", schema.get_table_names())
            self.assertIn("login_challenges", schema.get_table_names())
            self.assertIn(
                "user_id",
                {column["name"] for column in schema.get_columns("save_games")},
            )
        finally:
            engine.dispose()


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

    def test_scoped_auth_quota_has_independent_limit(self):
        runtime = RedisRuntime(rate_limit=0)

        self.assertEqual(runtime.allow_quota("auth:test", 1, 600), (True, 0))
        self.assertEqual(runtime.allow_quota("auth:test", 1, 600), (False, 0))
        self.assertEqual(runtime.allow("unlimited-game-runtime"), (True, -1))


if __name__ == "__main__":
    unittest.main()
