import unittest

from everstory.engine import WorldSession
from everstory.llm.client import LLMClient
from everstory.llm.intent import parse_actions
from everstory.pipeline import TurnPipeline
from everstory.worlds import load_world


class IntentTest(unittest.TestCase):
    def setUp(self):
        self.client = LLMClient(mode="stub")

    def test_parse_structured_actions(self):
        self.assertEqual(
            parse_actions("take rusty key", "ctx", self.client),
            [{"type": "take", "params": {"item": "rusty key"}}],
        )

    def test_parse_use_action(self):
        self.assertEqual(
            parse_actions("use rusty key on chest", "ctx", self.client),
            [
                {
                    "type": "use",
                    "params": {"item": "rusty key", "target": "chest"},
                }
            ],
        )

    def test_parse_give_action(self):
        self.assertEqual(
            parse_actions("give oil can to mara", "ctx", self.client),
            [
                {
                    "type": "give",
                    "params": {"item": "oil can", "recipient": "mara"},
                }
            ],
        )

    def test_dual_endpoint_routing(self):
        client = LLMClient(
            mode="stub",
            strong_model="qwen-plus",
            cheap_model="deepseek-chat",
            strong_base_url="https://qwen.test/v1",
            strong_api_key="kq",
            cheap_base_url="https://deepseek.test/v1",
            cheap_api_key="kd",
        )
        self.assertEqual(client.strong_base_url, "https://qwen.test/v1")
        self.assertEqual(client.cheap_api_key, "kd")
        # stub mode does not hit the network; the reply is a short fixed string
        reply = client.chat([{"role": "user", "content": "hi"}], model="deepseek-chat")
        self.assertEqual(reply, "[stub] ok")


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.session = WorldSession(load_world("lost_lighthouse"))
        self.pipeline = TurnPipeline(self.session, LLMClient(mode="stub"))

    def test_rejected_action_is_grounded(self):
        self.pipeline.process("move to lighthouse_ground")
        res = self.pipeline.process("open chest")
        self.assertFalse(res.results[0].ok)
        self.assertIn("locked", res.narration.lower())
        self.assertEqual(res.rejected, ["The iron chest is locked."])

    def test_successful_action_narrates_grounded_delta(self):
        res = self.pipeline.process("move to lighthouse_ground")
        self.assertTrue(res.results[0].ok)
        self.assertIn("Lighthouse Ground Floor", res.narration)

    def test_full_quest_via_pipeline(self):
        steps = [
            "move to lighthouse_ground",
            "move to cliff_path",
            "move to cave",
            "take rusty key",
            "move to cliff_path",
            "move to lighthouse_ground",
            "use rusty key on chest",
            "open chest",
            "take flint",
            "move to cottage",
            "move to dock",
            "move to boat_shed",
            "take oil can",
            "move to dock",
            "move to cottage",
            "use oil can on lantern",
            "use flint on lantern",
        ]
        for step in steps:
            res = self.pipeline.process(step)
            self.assertTrue(
                all(r.ok for r in res.results), f"{step}: {res.narration}"
            )
        self.assertTrue(self.session.state.flags["lighthouse_lit"])


if __name__ == "__main__":
    unittest.main()
