import tempfile
import unittest
from pathlib import Path

from everstory.engine import WorldSession
from everstory.models import Action
from everstory.persistence import (
    list_saves,
    load_session,
    load_session_bundle,
    save_session,
    session_from_dict,
    session_to_dict,
)
from everstory.worlds import load_world


def new_session() -> WorldSession:
    return WorldSession(load_world("lost_lighthouse"))


def act(session, action_type, **params):
    return session.act(
        Action(action_type=action_type, actor_id=session.player_id(), params=params)
    )


class PersistenceTest(unittest.TestCase):
    def test_dict_roundtrip(self):
        s = new_session()
        act(s, "move", to="lighthouse_ground")
        act(s, "move", to="cliff_path")
        act(s, "move", to="cave")
        act(s, "take", item="rusty_key")
        h0 = s.state.snapshot_hash()

        s2 = session_from_dict(session_to_dict(s))
        self.assertEqual(s2.state.snapshot_hash(), h0)
        self.assertEqual(s2.state.turn, s.state.turn)
        self.assertEqual(len(s2.history), len(s.history))
        self.assertEqual(
            s2.state.entity("rusty_key").owner_id, s.state.entity("rusty_key").owner_id
        )

    def test_save_and_load_file(self):
        s = new_session()
        act(s, "wait")
        with tempfile.TemporaryDirectory() as tmp:
            path = save_session(s, "test-save", saves_dir=tmp)
            self.assertTrue(Path(path).exists())
            saves = list_saves(tmp)
            self.assertEqual(len(saves), 1)
            self.assertTrue(saves[0]["name"].startswith("test-save"))

            s2 = load_session(path)
            self.assertEqual(s2.state.snapshot_hash(), s.state.snapshot_hash())
            self.assertEqual(s2.state.turn, s.state.turn)

    def test_save_bundle_roundtrips_optional_runtime_memory(self):
        s = new_session()
        extra = {"team_chat": {"version": 1, "messages": [], "evidence": [{"id": "clue-1"}]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = save_session(s, "bundle", saves_dir=tmp, extra=extra)
            restored, restored_extra = load_session_bundle(path)
            self.assertEqual(restored.state.snapshot_hash(), s.state.snapshot_hash())
            self.assertEqual(restored_extra, extra)
            self.assertEqual(list_saves(tmp)[0]["evidence"], 1)

    def test_talk_dialogue_and_ending(self):
        s = new_session()
        # Mara's default line before anything happens
        act(s, "move", to="lighthouse_ground")
        res = act(s, "talk", target="mara")
        self.assertTrue(res.ok)
        self.assertIn("light has been out", res.message)

        # Complete the light quest first (the oil can stays in inventory after
        # being used on the lantern).
        act(s, "move", to="cliff_path")
        act(s, "move", to="cave")
        act(s, "take", item="rusty_key")
        act(s, "move", to="cliff_path")
        act(s, "move", to="lighthouse_ground")
        act(s, "use", item="rusty_key", target="chest")
        act(s, "open", target="chest")
        act(s, "take", item="flint")
        act(s, "move", to="cottage")
        act(s, "move", to="dock")
        act(s, "move", to="boat_shed")
        act(s, "take", item="oil_can")
        act(s, "move", to="dock")
        act(s, "move", to="cottage")
        act(s, "use", item="oil_can", target="lantern")
        act(s, "use", item="flint", target="lantern")
        self.assertTrue(s.state.flags["lighthouse_lit"])
        self.assertFalse(s.state.flags.get("ending"))  # secret not yet learned

        # Now the gift + dialogue path reveals the secret and unlocks the ending.
        act(s, "move", to="lighthouse_ground")
        act(s, "give", item="oil_can", recipient="mara")
        self.assertTrue(s.state.flags["gave_oil"])
        res = act(s, "talk", target="mara")
        self.assertIn("last one disappeared", res.message)
        self.assertTrue(s.state.flags["learned_secret"])
        self.assertTrue(s.state.flags["ending"])


if __name__ == "__main__":
    unittest.main()
