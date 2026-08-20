import unittest

from everstory.eval.runner import run_eval, state_answer
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


if __name__ == "__main__":
    unittest.main()
