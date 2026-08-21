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


if __name__ == "__main__":
    unittest.main()
