import tempfile
import unittest
from pathlib import Path

from everstory.eval.episodes import EPISODES
from everstory.learn.__main__ import collect, main
from everstory.learn.inducer import evaluate, induce, predict, readable


class InducerTest(unittest.TestCase):
    def test_induce_recovers_move_rule(self):
        transitions = collect(EPISODES)
        rules = induce(transitions)
        move = next(r for r in rules if r.action_type == "move")
        self.assertIn("connected($here,$to)", move.preconditions)
        self.assertIn("at($actor,$to)", move.effects_added)
        self.assertEqual(move.time_delta, 1)

    def test_induce_recovers_take_rule(self):
        transitions = collect(EPISODES)
        rules = induce(transitions)
        take = next(r for r in rules if r.action_type == "take")
        self.assertIn("at($item,$here)", take.preconditions)
        self.assertIn("owner($item,$actor)", take.effects_added)
        self.assertIn("unowned($item)", take.effects_removed)

    def test_composite_actions_induce_pair_rules(self):
        transitions = collect(EPISODES)
        rules = induce(transitions)
        use = next(r for r in rules if r.action_type == "use")
        self.assertIn("rusty_key -> chest", use.pair_rules)
        chest_rule = use.pair_rules["rusty_key -> chest"]
        self.assertIn("locked($target)", chest_rule.preconditions)
        self.assertIn("not_locked($target)", chest_rule.effects_added)

    def test_evaluation_accuracy(self):
        transitions = collect(EPISODES)
        rules = induce(transitions)
        report = evaluate(rules, transitions)
        self.assertEqual(report["correct"], report["total"])
        self.assertEqual(report["accuracy"], 1.0)

    def test_failures_are_negative_examples(self):
        transitions = collect(EPISODES)
        failed = [t for t in transitions if not t["ok"]]
        self.assertTrue(failed, "failure exploration should produce negatives")
        move = next(r for r in induce(transitions) if r.action_type == "move")
        self.assertGreaterEqual(move.negatives, 1)

    def test_predict_counterfactual(self):
        transitions = collect(EPISODES)
        rules = induce(transitions)
        take = next(r for r in rules if r.action_type == "take")
        # The learned precondition is at($item,$here): the item must be in the
        # current location.
        self.assertFalse(predict(take, {"unowned($item)"}, {"item": "rusty_key"}))
        self.assertTrue(predict(take, {"at($item,$here)"}, {"item": "rusty_key"}))

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "learned-rules.md"
            old = __import__("sys").argv
            try:
                __import__("sys").argv = ["learn", "--out", str(out)]
                self.assertEqual(main(), 0)
            finally:
                __import__("sys").argv = old
            content = out.read_text(encoding="utf-8")
            self.assertIn("Learned rules", content)
            self.assertIn("move", content)

    def test_readable_render(self):
        transitions = collect(EPISODES)
        rules = induce(transitions)
        text = readable(next(r for r in rules if r.action_type == "take"))
        self.assertIn("take", text)
        self.assertIn("valid if", text)


if __name__ == "__main__":
    unittest.main()
