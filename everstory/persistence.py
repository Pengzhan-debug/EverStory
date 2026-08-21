"""Save and load world sessions to JSON files."""

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

from .engine import WorldSession
from .models import Action, EventRecord, WorldState
from .worlds import load_world

SAVES_DIR = Path("saves")


def session_to_dict(session: WorldSession) -> dict:
    state = session.state
    return {
        "version": 1,
        "world": session.world_name,
        "title": session.title,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "state": state.to_dict(),
        "history": [
            {
                "turn": h.turn,
                "actor": h.actor_id,
                "action": h.action.to_dict(),
                "ok": h.ok,
                "message": h.message,
                "state_hash": h.state_hash,
            }
            for h in session.history
        ],
    }


def session_from_dict(
    data: dict, collect_transitions: bool = False
) -> WorldSession:
    session = WorldSession(
        load_world(data.get("world", "lost_lighthouse")),
        collect_transitions=collect_transitions,
    )
    session.title = data.get("title", session.title)
    session.state = WorldState.from_dict(data["state"])
    session.history = [
        EventRecord(
            turn=h["turn"],
            actor_id=h["actor"],
            action=Action.from_dict(h["action"]),
            ok=h["ok"],
            message=h["message"],
            state_hash=h["state_hash"],
        )
        for h in data.get("history", [])
    ]
    # Only the current turn is snapshotted after a load (rollback history is
    # not persisted).
    session.snapshots = {
        session.state.turn: (copy.deepcopy(session.state), session.state.snapshot_hash())
    }
    return session


def save_session(
    session: WorldSession, name: str = "autosave", saves_dir=SAVES_DIR
) -> Path:
    saves_dir = Path(saves_dir)
    saves_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "save"
    path = saves_dir / f"{slug}-{int(time.time())}.json"
    path.write_text(
        json.dumps(session_to_dict(session), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def list_saves(saves_dir=SAVES_DIR) -> list[dict]:
    saves_dir = Path(saves_dir)
    if not saves_dir.exists():
        return []
    out: list[dict] = []
    for path in sorted(
        saves_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "turn": int(data.get("state", {}).get("turn", 0)),
                    "title": data.get("title", ""),
                    "saved_at": data.get("saved_at", ""),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    return out


def load_session(path, collect_transitions: bool = False) -> WorldSession:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return session_from_dict(data, collect_transitions=collect_transitions)
