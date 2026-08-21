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


if __name__ == "__main__":
    unittest.main()
