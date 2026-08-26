import unittest

from everstory.eval.episodes import long_wander
from everstory.eval.runner import run_eval, run_long_eval, state_answer
from everstory.llm.client import LLMClient
from everstory.worlds import load_world
from everstory.engine import WorldSession


class EvalTest(unittest.TestCase):
    def test_stub_eval_runs_and_scores(self):
        client = LLMClient(mode="stub")
        results = run_eval(client)
        self.assertTrue(results)
        everstory = [
            r for r in results if r.baseline == "everstory"
        ]
        self.assertEqual(len(everstory), 3)
        self.assertTrue(all(r.recall == 1.0 for r in everstory))
        self.assertTrue(all(r.total >= 1 for r in results))

    def test_state_answer_reads_ground_truth(self):
        session = WorldSession(load_world("lost_lighthouse"))
        self.assertEqual(state_answer(session, "Is the lighthouse lit?"), "no")
        self.assertEqual(
            state_answer(session, "Where is the rusty key?"), "sea cave"
        )

    def test_provider_label(self):
        client = LLMClient(mode="stub")
        results = run_eval(client, provider="qwen")
        self.assertTrue(results)
        self.assertTrue(all(r.provider == "qwen" for r in results))

    def test_markdown_has_provider_summary(self):
        client = LLMClient(mode="stub")
        from everstory.eval.runner import to_markdown

        markdown = to_markdown(run_eval(client), mode="stub")
        self.assertIn("Provider summary", markdown)
        self.assertIn("| Provider |", markdown)

    def test_long_wander_generation(self):
        episode = long_wander(30)
        self.assertEqual(len(episode.steps), 30)
        self.assertEqual(len(episode.facts), 3)
        self.assertEqual(episode.steps[0], "move to lighthouse_ground")

    def test_long_eval_stub_records_checkpoints(self):
        client = LLMClient(mode="stub")
        results = run_long_eval(client, horizon=30)
        self.assertEqual(len(results), 3)
        everstory = next(r for r in results if r["baseline"] == "everstory")
        self.assertEqual(set(everstory["checkpoints"]), {10, 20, 30})
        self.assertTrue(
            all(v == 1.0 for v in everstory["checkpoints"].values())
        )
        self.assertIsNone(everstory["contradictions"])

    def test_long_markdown_render(self):
        from everstory.eval.runner import to_long_markdown

        client = LLMClient(mode="stub")
        markdown = to_long_markdown(run_long_eval(client, horizon=15))
        self.assertIn("Long-horizon memory decay", markdown)
        self.assertIn("everstory", markdown)

    def test_team_eval_covers_authority_evidence_memory_and_case_completion(self):
        from everstory.eval.team import run_team_eval

        result = run_team_eval(LLMClient(mode="stub"), provider="offline-stub")
        self.assertEqual(result.proposal_accuracy, 1.0)
        self.assertEqual(result.approval_success, 1.0)
        self.assertEqual(result.unauthorized_mutations, 0)
        self.assertTrue(result.stale_task_blocked)
        self.assertEqual(result.evidence_grounding, 1.0)
        self.assertGreaterEqual(result.challenge_messages, 1)
        self.assertTrue(result.case_solved)
        self.assertTrue(result.memory_roundtrip)
        self.assertGreater(result.memory_bytes, 0)
        self.assertEqual(result.calls, 0)

    def test_team_eval_markdown_is_resume_ready(self):
        from everstory.eval.team import run_team_eval, to_team_markdown

        markdown = to_team_markdown(run_team_eval(LLMClient(mode="stub")))
        self.assertIn("Overall verdict: **PASS**", markdown)
        self.assertIn("Structured proposal accuracy", markdown)
        self.assertIn("Unauthorized world mutations", markdown)
        self.assertIn("Per-agent model usage", markdown)

    def test_team_eval_aggregates_real_mode_usage_by_agent(self):
        from everstory.eval.team import run_team_eval

        client = LLMClient(mode="api", strong_api_key="test", cheap_api_key="test")

        def metered_chat(*args, **kwargs):
            agent = kwargs.get("agent") or "unassigned"
            client.call_history.append({
                "agent": agent,
                "connection_id": client.agent_routes.get(agent, "reasoning"),
                "model": "metered-model",
                "latency_ms": 20,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "ok": True,
                "error": "",
            })
            return "Grounded hypothesis; request player approval before action."

        client.chat = metered_chat
        result = run_team_eval(client, provider="metered")
        self.assertEqual(result.calls, 12)
        self.assertEqual(result.prompt_tokens, 120)
        self.assertEqual(result.completion_tokens, 60)
        self.assertEqual(result.per_agent["field_investigator"]["calls"], 8)
        self.assertEqual(result.per_agent["case_director"]["calls"], 1)
        self.assertEqual(result.per_agent["case_analyst"]["calls"], 2)
        self.assertEqual(result.per_agent["skeptic"]["calls"], 1)


if __name__ == "__main__":
    unittest.main()
