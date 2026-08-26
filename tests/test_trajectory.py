import unittest

from everstory.engine import WorldSession
from everstory.models import Action
from everstory.trajectory import extract_facts
from everstory.worlds import load_world


class TrajectoryTest(unittest.TestCase):
    def setUp(self):
        self.s = WorldSession(load_world("lost_lighthouse"), collect_transitions=True)
        self.p = self.s.player_id()

    def act(self, action_type, **params):
        return self.s.act(
            Action(action_type=action_type, actor_id=self.p, params=params)
        )

    def test_transitions_recorded(self):
        res = self.act("move", to="lighthouse_ground")
        self.assertTrue(res.ok)
        self.assertEqual(len(self.s.transitions), 1)
        t = self.s.transitions[0]
        self.assertEqual(t["action_type"], "move")
        self.assertTrue(t["ok"])
        self.assertIn("connected($here,$to)", t["before"])
        self.assertIn("at($actor,$to)", t["after"])

    def test_failed_transitions_recorded(self):
        res = self.act("take", item="rusty_key")
        self.assertFalse(res.ok)
        t = self.s.transitions[-1]
        self.assertFalse(t["ok"])
        self.assertIn("unowned($item)", t["before"])

    def test_fact_extraction_abstracts_roles(self):
        action = Action("use", self.p, {"item": "oil_can", "target": "lantern"})
        facts, _ = extract_facts(self.s.state, action)
        self.assertIn("at($item,boat_shed)", facts)  # oil can is at the boat shed
        self.assertIn("at($target,cottage)", facts)  # lantern is in the cottage, not on the shore
        self.assertIn("unowned($item)", facts)
        self.assertIn("not_filled($target)", facts)


if __name__ == "__main__":
    unittest.main()
