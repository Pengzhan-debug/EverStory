"""Regression coverage for the September gameplay/concurrency review."""

import os
import socket
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, get_ident
from unittest.mock import patch

from fastapi.testclient import TestClient

from everstory.agents import TeamChatSession
from everstory.api.main import create_app, world_payload
from everstory.engine import WorldSession
from everstory.llm.dialogue import npc_reply_stub
from everstory.llm.transport import post_completion, validate_endpoint
from everstory.models import Action
from everstory.pipeline import TurnPipeline
from everstory.redis_runtime import RedisRuntime
from everstory.storage import DatabaseStorage, RuntimeConflict
from everstory.worlds import load_world


class GameplayRegressionTests(unittest.TestCase):
    def setUp(self):
        self.world = WorldSession(load_world("lost_lighthouse"))

    def act(self, kind, **params):
        return self.world.act(Action(kind, self.world.player_id(), params))

    def test_npc_cannot_be_taken(self):
        self.act("move", to="cottage")
        self.assertFalse(self.act("take", item="celia").ok)
        self.assertEqual(self.world.state.entity("celia").location_id, "cottage")
        self.assertTrue(self.act("talk", target="celia").ok)

    def test_player_view_does_not_reveal_remote_or_closed_container_items(self):
        self.assertEqual(world_payload(self.world)["items"], [])
        self.act("move", to="cottage")
        items = {item["id"] for item in world_payload(self.world)["items"]}
        self.assertIn("tide_chart", items)
        self.assertNotIn("salvage_ledger", items)
        self.assertNotIn("flint", items)
        self.assertIn("flint", {item["id"] for item in world_payload(self.world, reveal_unseen=True)["items"]})

    def test_unknown_or_missing_targets_are_failed_actions(self):
        for kind, params in (("take", {"item": "not_an_entity"}), ("take", {}),
                             ("talk", {"target": "missing"}), ("use", {"item": "missing", "target": "lantern"})):
            with self.subTest(kind=kind, params=params):
                self.assertFalse(self.act(kind, **params).ok)

    def test_remote_use_is_rejected_but_local_use_succeeds(self):
        self.world.state.entity("player").location_id = "boat_shed"
        self.assertTrue(self.act("take", item="oil_can").ok)
        self.assertFalse(self.act("use", item="oil_can", target="lantern").ok)
        self.assertFalse(self.world.state.entity("lantern").attributes["filled"])
        self.world.state.entity("player").location_id = "cottage"
        self.assertTrue(self.act("use", item="oil_can", target="lantern").ok)

    def test_carried_evidence_can_be_proposed_and_approved(self):
        self.act("move", to="cottage")
        self.assertTrue(self.act("take", item="tide_chart").ok)
        view = world_payload(self.world)
        team = TeamChatSession()
        task = team._propose_task("field_investigator", view, "examine tide_chart")
        self.assertEqual(task["action"], {"type": "examine", "params": {"target": "tide_chart"}})
        team._validate_executable_task(task, view)
        self.assertTrue(self.act("examine", target="tide_chart").ok)
        self.assertTrue(self.world.state.flags["verified_tide_timeline"])
        self.world.state.entity("tide_chart").owner_id = "celia"
        with self.assertRaises(ValueError):
            team._validate_executable_task(task, world_payload(self.world))

    def test_every_lighthouse_testimony_has_a_chinese_translation(self):
        for character in self.world.state.entities.values():
            for key, line in character.attributes.get("dialogue", {}).items():
                with self.subTest(character=character.id, key=key):
                    expected = character.attributes["dialogue_zh"][key]
                    self.assertEqual(npc_reply_stub(character, canonical_line=line, locale="zh-CN"), expected)
                    self.assertIn(line, npc_reply_stub(character, canonical_line=line, locale="en"))
        celia = self.world.state.entity("celia")
        self.assertIn("十一点", npc_reply_stub(celia, locale="zh-CN"))

    def test_untranslated_custom_testimony_is_not_discarded(self):
        celia = self.world.state.entity("celia")
        self.assertEqual(npc_reply_stub(celia, canonical_line="Custom evidence.", locale="zh-CN"), "Custom evidence.")

    def test_old_save_without_localization_still_preserves_chinese_evidence(self):
        celia = self.world.state.entity("celia")
        celia.attributes.pop("dialogue_zh")
        self.assertIn("十一点", npc_reply_stub(celia, locale="zh-CN"))


class RuntimeRegressionTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"LLM_MODE": "stub"})
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = DatabaseStorage(f"sqlite:///{Path(self.tmp.name).as_posix()}/runtime.sqlite")
        self.redis = RedisRuntime()
        self.a = TestClient(create_app(self.storage, self.redis))
        self.a.get("/api/world")
        self.a.headers["X-CSRF-Token"] = self.a.cookies.get("everstory_csrf")
        self.b = TestClient(create_app(self.storage, self.redis))
        self.b.cookies.update(self.a.cookies)
        self.b.headers.update(self.a.headers)

    def tearDown(self):
        self.a.close()
        self.b.close()
        self.storage.engine.dispose()
        self.tmp.cleanup()
        self.env.stop()

    def test_two_workers_refresh_before_writing(self):
        self.assertEqual(self.b.get("/api/world").json()["turn"], 0)
        self.assertEqual(self.a.post("/api/turn", json={"text": "move to cottage"}).json()["turn"], 1)
        self.assertEqual(self.b.get("/api/world").json()["turn"], 1)
        self.assertEqual(self.b.post("/api/turn", json={"text": "move to dock"}).json()["turn"], 2)
        self.assertEqual(self.a.get("/api/world").json()["turn"], 2)

    def test_storage_rejects_stale_revision(self):
        identity = self.a.get("/api/auth/session").json()
        user, runtime = identity["user"]["id"], identity["runtime_id"]
        payload = {"example": True}
        first = self.storage.save_runtime(user, runtime, payload, expected_revision=0)
        self.assertEqual(first, 1)
        with self.assertRaises(RuntimeConflict):
            self.storage.save_runtime(user, runtime, {"stale": True}, expected_revision=0)
        self.assertNotIn("stale", self.storage.load_runtime(user, runtime))

    def test_reset_waits_for_inflight_turn_and_remains_durable(self):
        entered, release, reset_started = Event(), Event(), Event()
        original = TurnPipeline.process

        def delayed(pipeline, *args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test turn never released")
            return original(pipeline, *args, **kwargs)

        def reset():
            reset_started.set()
            return self.b.post("/api/reset")

        with patch.object(TurnPipeline, "process", delayed), ThreadPoolExecutor(max_workers=2) as pool:
            turn = pool.submit(self.a.post, "/api/turn", json={"text": "move to cottage"})
            try:
                self.assertTrue(entered.wait(3))
                reset_future = pool.submit(reset)
                self.assertTrue(reset_started.wait(3))
                with self.assertRaises(TimeoutError):
                    reset_future.result(timeout=0.15)
            finally:
                release.set()
            self.assertEqual(turn.result(timeout=5).status_code, 200)
            self.assertEqual(reset_future.result(timeout=5).status_code, 200)
        fresh = TestClient(create_app(self.storage, self.redis))
        try:
            fresh.cookies.update(self.a.cookies)
            self.assertEqual(fresh.get("/api/world").json()["turn"], 0)
        finally:
            fresh.close()

    def test_stream_does_not_claim_completion_when_commit_fails(self):
        with patch.object(self.storage, "save_runtime", side_effect=RuntimeConflict("stale request")):
            response = self.a.post("/api/turn/stream", json={"text": "move to cottage"})
        self.assertIn('"type": "error"', response.text)
        self.assertNotIn('"type": "done"', response.text)
        self.assertEqual(self.a.get("/api/world").json()["turn"], 0)

    def test_stream_execution_and_commit_stay_on_one_worker(self):
        threads = []
        process = TurnPipeline.process_stream
        save = self.storage.save_runtime

        def tracked_process(pipeline, *args, **kwargs):
            for event in process(pipeline, *args, **kwargs):
                threads.append(get_ident())
                yield event

        def tracked_save(*args, **kwargs):
            threads.append(get_ident())
            return save(*args, **kwargs)

        with patch.object(TurnPipeline, "process_stream", tracked_process), patch.object(self.storage, "save_runtime", tracked_save):
            response = self.a.post("/api/turn/stream", json={"text": "move to cottage"})
        self.assertIn('"type": "done"', response.text)
        self.assertNotIn('"type": "error"', response.text)
        self.assertGreater(len(threads), 1)
        self.assertEqual(len(set(threads)), 1)

    def test_load_after_turn_is_visible_to_other_worker(self):
        saved = self.a.post("/api/save", json={"name": "before"}).json()
        self.b.post("/api/turn", json={"text": "move to cottage"})
        loaded = self.a.post("/api/load", json={"path": saved["path"]})
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(self.b.get("/api/world").json()["turn"], 0)


class EndpointPolicyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"LLM_ALLOW_PRIVATE_ENDPOINTS": "false"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_private_endpoints_are_rejected(self):
        for url in ("http://localhost:11434/v1", "https://127.0.0.1", "https://10.0.0.1",
                    "https://169.254.169.254", "https://[::1]", "https://[::ffff:127.0.0.1]",
                    "https://service.local", "https://user:pass@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_endpoint(url)

    def test_private_dns_answer_is_blocked_before_post(self):
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443))]), patch("requests.Session") as session:
            with self.assertRaises(ValueError):
                post_completion("https://model.example/v1", json={})
            session.return_value.post.assert_not_called()

    def test_connection_is_pinned_and_redirects_and_proxies_disabled(self):
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]) as dns, patch("requests.Session") as factory:
            session = factory.return_value
            post_completion("https://model.example/v1/chat/completions", json={}, headers={"Authorization": "Bearer test"})
            args, kwargs = session.post.call_args
            self.assertEqual(args[0], "https://8.8.8.8:443/v1/chat/completions")
            self.assertEqual(kwargs["headers"]["Host"], "model.example")
            self.assertFalse(kwargs["allow_redirects"])
            self.assertFalse(session.trust_env)
            adapter = session.mount.call_args.args[1]
            self.assertEqual(adapter.poolmanager.connection_pool_kw["assert_hostname"], "model.example")
            self.assertEqual(adapter.poolmanager.connection_pool_kw["server_hostname"], "model.example")
            self.assertEqual(dns.call_count, 1)

    def test_local_models_require_explicit_operator_opt_in(self):
        with patch.dict(os.environ, {"LLM_ALLOW_PRIVATE_ENDPOINTS": "true"}):
            self.assertEqual(validate_endpoint("http://localhost:11434/v1").hostname, "localhost")
