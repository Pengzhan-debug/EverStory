import unittest
from unittest.mock import Mock, patch

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

    def test_explicit_role_routes_same_model_to_correct_endpoint(self):
        client = LLMClient(
            mode="api",
            strong_model="shared-model",
            cheap_model="shared-model",
            strong_base_url="https://reasoning.test/v1",
            strong_api_key="reasoning-key",
            cheap_base_url="https://story.test/v1",
            cheap_api_key="story-key",
        )
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        with patch("requests.post", return_value=response) as post:
            client.chat(
                [{"role": "user", "content": "hi"}],
                model="shared-model",
                role="cheap",
            )
        self.assertEqual(post.call_args.args[0], "https://story.test/v1/chat/completions")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"], "Bearer story-key"
        )

    def test_agent_route_overrides_legacy_role(self):
        client = LLMClient(
            mode="api",
            strong_model="legacy-strong",
            cheap_model="legacy-cheap",
            strong_base_url="https://legacy.test/v1",
            strong_api_key="legacy-key",
            connections={
                "analyst": {
                    "name": "Analyst",
                    "base_url": "https://analyst.test/v1",
                    "api_key": "analyst-key",
                    "model": "analysis-model",
                }
            },
            agent_routes={"case_analyst": "analyst"},
        )
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }
        with patch("requests.post", return_value=response) as post:
            client.chat(
                [{"role": "user", "content": "analyze"}],
                role="cheap",
                agent="case_analyst",
            )
        self.assertEqual(post.call_args.args[0], "https://analyst.test/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "analysis-model")
        self.assertEqual(client.call_history[-1]["prompt_tokens"], 5)


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

    def test_talk_uses_npc_dialogue(self):
        self.pipeline.process("move to lighthouse_ground")
        res = self.pipeline.process("talk to mara")
        self.assertTrue(res.results[0].ok)
        self.assertTrue(res.narration.startswith("Mara:"))

    def test_chat_with_nearby_npc(self):
        self.pipeline.process("move to lighthouse_ground")
        res = self.pipeline.process("hello, who are you?")
        self.assertEqual(res.results, [])
        self.assertIn("Mara", res.narration)

    def test_process_stream_yields_done_with_world(self):
        events = list(
            self.pipeline.process_stream(
                "move to lighthouse_ground",
                world_renderer=lambda s: {"turn": s.state.turn},
            )
        )
        text = "".join(e.get("delta", "") for e in events if e["type"] == "text")
        done = [e for e in events if e["type"] == "done"][0]
        self.assertIn("Lighthouse Ground Floor", text)
        self.assertEqual(done["world"], {"turn": 1})


if __name__ == "__main__":
    unittest.main()
