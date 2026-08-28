import unittest
from unittest.mock import Mock, patch

from everstory.engine import WorldSession
from everstory.llm.client import LLMClient, LLMError
from everstory.llm.intent import parse_actions
from everstory.llm.language import ensure_output_locale, guarded_stream, matches_locale
from everstory.llm.usage import usage_payload
from everstory.pipeline import TurnPipeline
from everstory.worlds import load_world


class IntentTest(unittest.TestCase):
    def test_explicit_command_bypasses_live_intent_model(self):
        client = LLMClient(mode="api", api_key="unused")
        client.chat = lambda *args, **kwargs: self.fail("explicit command called the LLM")
        self.assertEqual(
            parse_actions("move to cottage", "world", client),
            [{"type": "move", "params": {"to": "cottage"}}],
        )

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

    def test_personal_route_never_falls_back_to_platform(self):
        client = LLMClient(
            mode="api",
            strong_api_key="platform-key",
            connections={
                "personal_api": {
                    "name": "Player API",
                    "base_url": "https://player.test/v1",
                    "api_key": "player-key",
                    "model": "player-model",
                    "credential_source": "personal",
                },
                "platform_api": {
                    "name": "Platform API",
                    "base_url": "https://platform.test/v1",
                    "api_key": "platform-key",
                    "model": "platform-model",
                    "credential_source": "platform",
                },
            },
            agent_routes={"case_analyst": "personal_api"},
        )
        failure = Mock(status_code=503, text="unavailable")
        with patch("requests.post", return_value=failure) as post, patch("time.sleep"):
            with self.assertRaises(LLMError):
                client.chat([{"role": "user", "content": "analyze"}], agent="case_analyst")
        self.assertEqual(post.call_count, 3)
        self.assertTrue(all(call.args[0].startswith("https://player.test") for call in post.call_args_list))
        self.assertEqual(client.call_history[-1]["credential_source"], "personal")

    def test_platform_quota_blocks_before_network_request(self):
        client = LLMClient(mode="api", strong_api_key="platform-key", platform_token_limit=10)
        client.call_history.append({
            "credential_source": "platform", "prompt_tokens": 8,
            "completion_tokens": 2, "ok": True,
        })
        with patch("requests.post") as post:
            with self.assertRaisesRegex(LLMError, "allowance exhausted"):
                client.chat([{"role": "user", "content": "hi"}], agent="case_director")
        post.assert_not_called()
        self.assertFalse(client.call_history[-1]["ok"])

    def test_usage_payload_groups_sources_and_keeps_quota_separate(self):
        client = LLMClient(mode="api", platform_token_limit=100)
        client.last_usage = {"prompt_tokens": 10, "completion_tokens": 5}
        client._record_call(agent="case_director", connection_id="reasoning", model="qwen", latency_ms=40, ok=True)
        client.connections["player"] = {
            "name": "Player", "base_url": "https://player.test/v1", "api_key": "key",
            "model": "custom", "credential_source": "personal",
            "input_cost_per_million": 1, "output_cost_per_million": 2,
        }
        client.last_usage = {"prompt_tokens": 20, "completion_tokens": 10}
        client._record_call(agent="narrator", connection_id="player", model="custom", latency_ms=60, ok=True)
        data = usage_payload(client, range_key="24h", metric="tokens", group_by="source")
        self.assertEqual(data["summary"]["total_tokens"], 45)
        self.assertEqual(data["summary"]["platform_quota"]["used"], 15)
        self.assertEqual(data["summary"]["personal_tokens"], 30)
        self.assertEqual({group["id"] for group in data["groups"]}, {"platform", "personal"})


class LanguageGuardTest(unittest.TestCase):
    def test_detects_material_output_language(self):
        self.assertTrue(matches_locale("灯塔外的海浪正在上涨。", "zh-CN"))
        self.assertFalse(matches_locale("The tide is rising outside the lighthouse.", "zh-CN"))
        self.assertTrue(matches_locale("The tide is rising outside the lighthouse.", "en"))

    def test_repairs_a_wrong_language_response(self):
        client = Mock()
        client.chat.return_value = "潮水正在上涨。"
        result = ensure_output_locale(
            client, "The tide is rising.", "zh-CN", agent="narrator"
        )
        self.assertEqual(result, "潮水正在上涨。")
        client.chat.assert_called_once()

    def test_wrong_language_stream_is_buffered_before_repair(self):
        client = Mock()
        client.chat.return_value = "守塔人拒绝继续猜测。"
        chunks = guarded_stream(
            client,
            iter(["The keeper ", "refuses to speculate."]),
            "zh-CN",
            agent="npc_dialogue",
        )
        self.assertEqual(list(chunks), ["守塔人拒绝继续猜测。"])


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
