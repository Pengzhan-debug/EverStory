import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
class ApiTest(unittest.TestCase):
    def setUp(self):
        from everstory.api.main import app

        self.client = TestClient(app)
        self.client.post("/api/reset")

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


if __name__ == "__main__":
    unittest.main()
