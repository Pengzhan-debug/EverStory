import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
class ApiTest(unittest.TestCase):
    def setUp(self):
        import os

        self._old_mode = os.environ.get("LLM_MODE")
        os.environ["LLM_MODE"] = "stub"  # keep tests offline/deterministic
        from everstory.api.main import app

        self.client = TestClient(app)
        self.client.post("/api/reset")

    def tearDown(self):
        import os

        if self._old_mode is None:
            os.environ.pop("LLM_MODE", None)
        else:
            os.environ["LLM_MODE"] = self._old_mode

    def test_health_and_world(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        world = self.client.get("/api/world").json()
        self.assertIn("locations", world)
        self.assertIn("player", world)
        self.assertIn("scene", world)
        self.assertEqual(world["scene"]["location"]["name"], "Keeper's Cottage")
        self.assertGreater(len(world["scene"]["suggestions"]), 1)

    def test_signal_console_and_session_settings(self):
        self.assertEqual(self.client.get("/settings").status_code, 200)
        initial = self.client.get("/api/llm/settings").json()
        self.assertEqual(initial["mode"], "stub")
        self.assertNotIn("api_key", str(initial))

        response = self.client.put(
            "/api/llm/settings",
            json={
                "mode": "stub",
                "strong": {
                    "base_url": "https://reasoning.test/v1",
                    "model": "same-model",
                    "api_key": "secret-strong-1234",
                },
                "cheap": {
                    "base_url": "https://story.test/v1",
                    "model": "same-model",
                    "api_key": "secret-cheap-5678",
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        raw = response.text
        self.assertNotIn("secret-strong", raw)
        self.assertNotIn("secret-cheap", raw)
        settings = response.json()["settings"]
        self.assertEqual(settings["strong"]["masked_key"], "••••••••1234")
        self.assertEqual(settings["cheap"]["masked_key"], "••••••••5678")

        # A new world keeps the active API route for this browser session.
        self.client.post("/api/reset")
        after_reset = self.client.get("/api/llm/settings").json()
        self.assertEqual(after_reset["strong"]["base_url"], "https://reasoning.test/v1")
        test = self.client.post("/api/llm/test", json={"role": "strong"}).json()
        self.assertTrue(test["ok"])

    def test_signal_console_rejects_insecure_remote_url(self):
        response = self.client.put(
            "/api/llm/settings",
            json={
                "strong": {
                    "base_url": "http://example.com/v1",
                    "model": "model",
                }
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("HTTPS", response.json()["error"])

    def test_agent_connection_pool_and_routes(self):
        initial = self.client.get("/api/llm/settings").json()
        routes = dict(initial["agent_routes"])
        routes["case_analyst"] = "analyst_api"
        response = self.client.put(
            "/api/llm/settings",
            json={
                "mode": "stub",
                "connections": {
                    "reasoning": {
                        "name": "Shared runtime",
                        "base_url": "https://runtime.test/v1",
                        "model": "runtime-model",
                    },
                    "story": {
                        "name": "Story runtime",
                        "base_url": "https://story.test/v1",
                        "model": "story-model",
                    },
                    "analyst_api": {
                        "name": "Analyst dedicated",
                        "base_url": "https://analyst.test/v1",
                        "model": "analysis-model",
                        "api_key": "analyst-secret-7788",
                    },
                },
                "agent_routes": routes,
            },
        )
        self.assertEqual(response.status_code, 200)
        settings = response.json()["settings"]
        self.assertEqual(settings["agent_routes"]["case_analyst"], "analyst_api")
        self.assertEqual(settings["connections"]["analyst_api"]["model"], "analysis-model")
        self.assertNotIn("analyst-secret", response.text)
        self.assertIn("diagnostics", settings)

    def test_team_chat_has_identity_and_agent_challenge(self):
        history = self.client.get("/api/agents/chat").json()
        participants = {member["id"]: member for member in history["participants"]}
        self.assertTrue(participants["player"]["human"])
        self.assertEqual(participants["player"]["role"], "Lead Investigator")
        self.assertIn("case_analyst", participants)
        self.assertIn("skeptic", participants)

        before_turn = self.client.get("/api/world").json()["turn"]
        response = self.client.post(
            "/api/agents/chat",
            json={"text": "I think the lighthouse failure proves sabotage."},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        created = data["new_messages"]
        self.assertEqual([message["sender_id"] for message in created], [
            "player", "case_analyst", "skeptic"
        ])
        self.assertEqual(created[0]["initials"], "YOU")
        self.assertEqual(created[2]["kind"], "challenge")
        self.assertEqual(created[2]["reply_to"], created[1]["id"])
        self.assertIn(created[1]["sender_name"], created[2]["text"])
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["status"], "proposed")
        self.assertEqual(created[1]["task_id"], data["tasks"][0]["id"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], before_turn)

    def test_player_approves_grounded_scene_inspection(self):
        before = self.client.get("/api/world").json()
        proposal = self.client.post(
            "/api/agents/chat",
            json={"text": "@field inspect the current scene and report confirmed evidence."},
        ).json()
        task = proposal["tasks"][0]
        self.assertEqual(task["agent_id"], "field_investigator")
        self.assertEqual(task["type"], "inspect_scene")
        self.assertEqual(task["status"], "proposed")
        self.assertEqual(proposal["evidence"], [])

        response = self.client.post(f"/api/agents/tasks/{task['id']}/approve")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        approved = next(item for item in result["tasks"] if item["id"] == task["id"])
        self.assertEqual(approved["status"], "completed")
        self.assertGreaterEqual(len(result["evidence"]), 1)
        self.assertTrue(all(
            item["location_id"] == before["player"]["location_id"]
            for item in result["evidence"]
        ))
        self.assertEqual(result["new_messages"][0]["kind"], "task_result")
        self.assertEqual(result["new_messages"][0]["task_id"], task["id"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], before["turn"])

        repeated = self.client.post(f"/api/agents/tasks/{task['id']}/approve")
        self.assertEqual(repeated.status_code, 400)

    def test_approved_agent_travel_executes_world_action(self):
        before = self.client.get("/api/world").json()
        proposal = self.client.post(
            "/api/agents/chat",
            json={"text": "@field travel to Dock with the team."},
        ).json()
        task = proposal["tasks"][0]
        self.assertEqual(task["type"], "travel")
        self.assertEqual(task["action"], {"type": "move", "params": {"to": "dock"}})
        self.assertEqual(self.client.get("/api/world").json()["turn"], before["turn"])

        approved = self.client.post(f"/api/agents/tasks/{task['id']}/approve").json()
        self.assertTrue(approved["action_result"]["ok"])
        self.assertEqual(approved["world"]["player"]["location_id"], "dock")
        self.assertEqual(approved["world"]["turn"], before["turn"] + 1)
        evidence = next(item for item in approved["evidence"] if item["task_id"] == task["id"])
        self.assertEqual(evidence["type"], "scene")

    def test_approved_agent_examine_and_interview_record_evidence(self):
        examine = self.client.post(
            "/api/agents/chat",
            json={"text": "@field examine the lantern."},
        ).json()["tasks"][0]
        self.assertEqual(examine["type"], "examine")
        examined = self.client.post(f"/api/agents/tasks/{examine['id']}/approve").json()
        self.assertIn("cold and dark", examined["action_result"]["message"])
        self.assertTrue(any(item["type"] == "item" for item in examined["evidence"]))

        self.client.post("/api/turn", json={"text": "move to lighthouse_ground"})
        interview = self.client.post(
            "/api/agents/chat",
            json={"text": "@field interview Mara."},
        ).json()["tasks"][-1]
        self.assertEqual(interview["type"], "interview")
        interviewed = self.client.post(f"/api/agents/tasks/{interview['id']}/approve").json()
        self.assertIn("sea has grown restless", interviewed["action_result"]["message"])
        self.assertTrue(any(item["type"] == "testimony" for item in interviewed["evidence"]))

    def test_stale_agent_action_requires_fresh_proposal(self):
        proposal = self.client.post(
            "/api/agents/chat", json={"text": "@field travel to Dock."}
        ).json()["tasks"][0]
        self.client.post("/api/turn", json={"text": "move to lighthouse_ground"})
        before = self.client.get("/api/world").json()["turn"]
        response = self.client.post(f"/api/agents/tasks/{proposal['id']}/approve")
        self.assertEqual(response.status_code, 400)
        self.assertIn("fresh proposal", response.json()["error"])
        self.assertEqual(self.client.get("/api/world").json()["turn"], before)

    def test_director_can_propose_authoritative_accusation(self):
        self.client.post("/api/turn", json={"text": "move to dock"})
        proposal = self.client.post(
            "/api/agents/chat",
            json={"text": "@director accuse Elias Ward using the current case."},
        ).json()
        task = proposal["tasks"][0]
        self.assertEqual(task["agent_id"], "case_director")
        self.assertEqual(task["type"], "accuse")
        self.assertEqual(task["action"]["params"]["target"], "elias")
        approved = self.client.post(f"/api/agents/tasks/{task['id']}/approve").json()
        self.assertEqual(approved["action_result"]["type"], "accuse")
        self.assertFalse(approved["world"]["flags"]["case_solved"])
        self.assertIn("required evidence", approved["action_result"]["message"])

    def test_team_chat_is_isolated_between_browser_sessions(self):
        other = TestClient(self.client.app)
        try:
            self.client.post("/api/agents/chat", json={"text": "private team note"})
            first = self.client.get("/api/agents/chat").json()["messages"]
            second = other.get("/api/agents/chat").json()["messages"]
            self.assertGreater(len(first), len(second))
            self.assertFalse(any("private team note" in item["text"] for item in second))
            self.assertEqual(other.get("/api/agents/chat").json()["tasks"], [])
        finally:
            other.close()

    def test_static_assets_are_cached_and_compressed(self):
        image = self.client.get("/static/img/scenes/cottage.webp")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/webp")
        self.assertIn("max-age=86400", image.headers.get("cache-control", ""))

        css = self.client.get(
            "/static/ui-tweaks.css", headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(css.status_code, 200)
        self.assertEqual(css.headers.get("content-encoding"), "gzip")

    def test_turn_rejects_invalid_action(self):
        data = self.client.post("/api/turn", json={"text": "move to cave"}).json()
        self.assertFalse(data["events"][0]["ok"])
        self.assertEqual(
            data["world"]["player"]["location_name"], "Keeper's Cottage"
        )

    def test_turn_applies_valid_action(self):
        data = self.client.post(
            "/api/turn", json={"text": "move to lighthouse_ground"}
        ).json()
        self.assertTrue(data["events"][0]["ok"])
        self.assertEqual(
            data["world"]["player"]["location_name"], "Lighthouse Ground Floor"
        )

    def test_clients_have_isolated_worlds(self):
        other = TestClient(self.client.app)
        try:
            self.client.post("/api/turn", json={"text": "wait"})
            first_world = self.client.get("/api/world").json()
            other_world = other.get("/api/world").json()
            self.assertEqual(first_world["turn"], 1)
            self.assertEqual(other_world["turn"], 0)
            self.assertNotEqual(
                self.client.cookies.get("everstory_session"),
                other.cookies.get("everstory_session"),
            )
        finally:
            other.close()

    def test_saves_are_isolated_by_client(self):
        import tempfile
        import everstory.persistence as persistence

        other = TestClient(self.client.app)
        original = persistence.SAVES_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                persistence.SAVES_DIR = tmp
                self.client.post("/api/save", json={"name": "private"})
                self.assertEqual(len(self.client.get("/api/saves").json()["saves"]), 1)
                self.assertEqual(other.get("/api/saves").json()["saves"], [])
        finally:
            persistence.SAVES_DIR = original
            other.close()

    def test_same_session_turns_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor

        other = TestClient(self.client.app)
        other.cookies.set(
            "everstory_session", self.client.cookies.get("everstory_session")
        )
        try:
            def wait_turn(client):
                return client.post("/api/turn", json={"text": "wait"}).json()["turn"]

            with ThreadPoolExecutor(max_workers=2) as pool:
                turns = list(pool.map(wait_turn, [self.client, other]))
            self.assertEqual(sorted(turns), [1, 2])
            self.assertEqual(self.client.get("/api/world").json()["turn"], 2)
        finally:
            other.close()

    def test_reset(self):
        self.client.post("/api/turn", json={"text": "wait"})
        self.client.post("/api/reset")
        world = self.client.get("/api/world").json()
        self.assertEqual(world["turn"], 0)
        self.assertEqual(world["player"]["location_name"], "Keeper's Cottage")

    def test_save_and_load(self):
        import tempfile
        from everstory.persistence import SAVES_DIR

        with tempfile.TemporaryDirectory() as tmp:
            original = SAVES_DIR
            import everstory.persistence as persistence

            persistence.SAVES_DIR = tmp
            try:
                self.client.post("/api/turn", json={"text": "wait"})
                saved = self.client.post(
                    "/api/save", json={"name": "apitest"}
                ).json()
                self.assertTrue(saved["ok"])
                self.client.post("/api/reset")
                world = self.client.get("/api/world").json()
                self.assertEqual(world["turn"], 0)

                saves = self.client.get("/api/saves").json()["saves"]
                self.assertGreaterEqual(len(saves), 1)
                loaded = self.client.post(
                    "/api/load", json={"path": saves[0]["path"]}
                ).json()
                self.assertGreater(loaded["turn"], 0)
            finally:
                persistence.SAVES_DIR = original

    def test_save_and_load_restores_investigation_memory(self):
        import tempfile
        import everstory.persistence as persistence

        original = persistence.SAVES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            persistence.SAVES_DIR = tmp
            try:
                proposal = self.client.post(
                    "/api/agents/chat",
                    json={"text": "@field inspect this scene for confirmed evidence"},
                ).json()
                task_id = proposal["tasks"][0]["id"]
                approved = self.client.post(
                    f"/api/agents/tasks/{task_id}/approve"
                ).json()
                evidence_ids = [item["id"] for item in approved["evidence"]]

                saved = self.client.post(
                    "/api/save", json={"name": "case-memory"}
                ).json()
                self.assertEqual(saved["evidence"], len(evidence_ids))
                self.client.post("/api/reset")
                self.assertEqual(
                    self.client.get("/api/agents/chat").json()["evidence"], []
                )

                loaded = self.client.post(
                    "/api/load", json={"path": saved["path"]}
                )
                self.assertEqual(loaded.status_code, 200)
                restored = self.client.get("/api/agents/chat").json()
                self.assertEqual(
                    [item["id"] for item in restored["evidence"]], evidence_ids
                )
                restored_task = next(
                    item for item in restored["tasks"] if item["id"] == task_id
                )
                self.assertEqual(restored_task["status"], "completed")
                self.assertTrue(any(
                    item.get("task_id") == task_id
                    and item["kind"] == "task_result"
                    for item in restored["messages"]
                ))
            finally:
                persistence.SAVES_DIR = original


if __name__ == "__main__":
    unittest.main()
