import unittest

from everstory.engine import WorldSession
from everstory.models import Action, EntityKind
from everstory.worlds import load_world


def new_session() -> WorldSession:
    return WorldSession(load_world("lost_lighthouse"))


def act(session: WorldSession, action_type: str, **params):
    return session.act(
        Action(action_type=action_type, actor_id=session.player_id(), params=params)
    )


class WorldIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.s = new_session()
        self.state = self.s.state

    def test_all_references_resolve(self):
        ids = set(self.state.entities)
        for e in self.state.entities.values():
            if e.location_id is not None:
                self.assertIn(e.location_id, ids, f"{e.id}: missing location")
            if e.owner_id is not None:
                self.assertIn(e.owner_id, ids, f"{e.id}: missing owner")
        for r in self.state.relationships:
            self.assertIn(r.source_id, ids, f"relationship source missing: {r}")
            self.assertIn(r.target_id, ids, f"relationship target missing: {r}")

    def test_connections_are_symmetric(self):
        for e in self.state.entities.values():
            for conn in e.attributes.get("connections", []):
                other = self.state.entities[conn]
                self.assertIn(
                    e.id,
                    other.attributes.get("connections", []),
                    f"{e.id} -> {conn} is not symmetric",
                )

    def test_single_player(self):
        players = [
            e
            for e in self.state.entities.values()
            if e.kind == EntityKind.CHARACTER and e.name.lower() == "you"
        ]
        self.assertEqual(len(players), 1)


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.s = new_session()
        self.p = self.s.player_id()

    def test_move_to_connected_location(self):
        res = act(self.s, "move", to="lighthouse_ground")
        self.assertTrue(res.ok, res.message)
        self.assertEqual(self.s.state.entity(self.p).location_id, "lighthouse_ground")

    def test_move_to_unreachable_rejected(self):
        res = act(self.s, "move", to="cave")
        self.assertFalse(res.ok)
        self.assertIn("can't go that way", res.message.lower())
        self.assertEqual(self.s.state.entity(self.p).location_id, "cottage")

    def test_take_item_not_here_rejected(self):
        res = act(self.s, "take", item="rusty_key")
        self.assertFalse(res.ok)
        self.assertIn("isn't here", res.message.lower())

    def test_take_updates_inventory(self):
        act(self.s, "move", to="lighthouse_ground")
        act(self.s, "move", to="cliff_path")
        act(self.s, "move", to="cave")
        res = act(self.s, "take", item="rusty_key")
        self.assertTrue(res.ok, res.message)
        ent = self.s.state.entity("rusty_key")
        self.assertEqual(ent.owner_id, self.p)
        self.assertIn("rusty key", self.s.inventory_summary(self.p))

    def test_locked_chest_rejected_without_key(self):
        act(self.s, "move", to="lighthouse_ground")
        res = act(self.s, "open", target="chest")
        self.assertFalse(res.ok)
        self.assertIn("locked", res.message.lower())

    def test_give_requires_ownership(self):
        res = act(self.s, "give", item="oil_can", recipient="mara")
        self.assertFalse(res.ok)
        self.assertIn("don't have", res.message.lower())

    def test_give_to_character_in_same_place(self):
        act(self.s, "move", to="dock")
        act(self.s, "move", to="boat_shed")
        act(self.s, "take", item="oil_can")
        act(self.s, "move", to="dock")
        act(self.s, "move", to="cottage")
        act(self.s, "move", to="lighthouse_ground")
        res = act(self.s, "give", item="oil_can", recipient="mara")
        self.assertTrue(res.ok, res.message)
        self.assertEqual(self.s.state.entity("oil_can").owner_id, "mara")

    def test_rejected_action_leaves_state_unchanged(self):
        h0 = self.s.state.snapshot_hash()
        res = act(self.s, "open", target="chest")
        self.assertFalse(res.ok)
        self.assertEqual(self.s.state.snapshot_hash(), h0)

    def test_rollback_restores_earlier_state(self):
        h0 = self.s.state.snapshot_hash()
        act(self.s, "move", to="lighthouse_ground")
        act(self.s, "move", to="cliff_path")
        self.assertNotEqual(self.s.state.snapshot_hash(), h0)
        self.s.rollback(0)
        self.assertEqual(self.s.state.snapshot_hash(), h0)
        self.assertEqual(self.s.state.turn, 0)

    def test_name_resolution(self):
        self.assertEqual(self.s.resolve_name("rusty key"), "rusty_key")
        self.assertEqual(self.s.resolve_name("Rusty"), "rusty_key")
        self.assertEqual(self.s.resolve_name("iron"), "chest")
        self.assertIsNone(self.s.resolve_name("nonexistent"))

    def test_full_quest_walkthrough(self):
        steps = [
            ("move", {"to": "lighthouse_ground"}),
            ("move", {"to": "cliff_path"}),
            ("move", {"to": "cave"}),
            ("take", {"item": "rusty_key"}),
            ("move", {"to": "cliff_path"}),
            ("move", {"to": "lighthouse_ground"}),
            ("use", {"item": "rusty_key", "target": "chest"}),
            ("open", {"target": "chest"}),
            ("take", {"item": "flint"}),
            ("move", {"to": "cottage"}),
            ("move", {"to": "dock"}),
            ("move", {"to": "boat_shed"}),
            ("take", {"item": "oil_can"}),
            ("move", {"to": "dock"}),
            ("move", {"to": "cottage"}),
            ("use", {"item": "oil_can", "target": "lantern"}),
            ("use", {"item": "flint", "target": "lantern"}),
        ]
        for action_type, params in steps:
            res = act(self.s, action_type, **params)
            self.assertTrue(res.ok, f"{action_type} {params}: {res.message}")
        self.assertTrue(self.s.state.flags["lighthouse_lit"])
        self.assertIn("[x]", self.s.quest_summary())


if __name__ == "__main__":
    unittest.main()
