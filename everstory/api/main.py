"""EverStory web API + static frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import build_role_client
from ..engine import WorldSession
from ..pipeline import TurnPipeline
from ..worlds import load_world

STATIC_DIR = Path(__file__).parent / "static"


def world_payload(session: WorldSession) -> dict:
    st = session.state
    actor_id = session.player_id()
    actor = st.entity(actor_id)
    loc = st.entity(actor.location_id)
    locations = [
        {
            "id": e.id,
            "name": e.name,
            "connections": e.attributes.get("connections", []),
            "current": e.id == actor.location_id,
        }
        for e in st.entities.values()
        if e.kind.value == "location"
    ]
    characters = [
        {
            "id": e.id,
            "name": e.name,
            "location_id": e.location_id,
            "description": e.description,
        }
        for e in st.entities.values()
        if e.kind.value == "character"
    ]
    items = [
        {
            "id": e.id,
            "name": e.name,
            "location_id": e.location_id,
            "owner_id": e.owner_id,
            "locked": bool(e.attributes.get("locked", False)),
            "lit": bool(e.attributes.get("lit", False)),
        }
        for e in st.entities.values()
        if e.kind.value == "item"
    ]
    relationships = [
        {"type": r.type, "from": r.source_id, "to": r.target_id}
        for r in st.relationships
    ]
    quests = [
        {
            "name": e.name,
            "done": bool(st.flags.get(e.attributes.get("flag", ""))),
        }
        for e in st.entities.values()
        if e.kind.value == "quest"
    ]
    inventory = [e.name for e in st.entities.values() if e.owner_id == actor_id]
    history = [
        {"turn": h.turn, "ok": h.ok, "message": h.message}
        for h in session.history[-40:]
    ]
    return {
        "title": session.title,
        "time": st.time,
        "turn": st.turn,
        "state_hash": st.snapshot_hash(),
        "flags": dict(st.flags),
        "player": {
            "name": actor.name,
            "location_id": actor.location_id,
            "location_name": loc.name,
            "inventory": inventory,
        },
        "locations": locations,
        "characters": characters,
        "items": items,
        "relationships": relationships,
        "quests": quests,
        "history": history,
    }


def create_app() -> FastAPI:
    app = FastAPI(title="EverStory", version="0.1.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    runtime = {"session": None, "pipeline": None}

    def ensure() -> None:
        if runtime["session"] is None:
            session = WorldSession(load_world("lost_lighthouse"))
            runtime["session"] = session
            runtime["pipeline"] = TurnPipeline(session, build_role_client())

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/reset")
    def reset():
        runtime["session"] = None
        runtime["pipeline"] = None
        ensure()
        return {"ok": True}

    @app.get("/api/world")
    def world():
        ensure()
        return world_payload(runtime["session"])

    @app.post("/api/turn")
    async def turn(request: Request):
        ensure()
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            return {
                "reply": "Say something.",
                "world": world_payload(runtime["session"]),
                "events": [],
            }
        result = runtime["pipeline"].process(text)
        return {
            "reply": result.narration,
            "turn": result.turn,
            "state_hash": result.state_hash,
            "events": [
                {
                    "type": r.action.action_type,
                    "ok": r.ok,
                    "message": r.message,
                }
                for r in result.results
            ],
            "world": world_payload(runtime["session"]),
        }

    return app


app = create_app()


def run() -> None:
    import uvicorn

    # Port 8123 avoids clashing with other local dev servers (e.g. AgentForge
    # uses 8000/8080).
    uvicorn.run("everstory.api.main:app", host="127.0.0.1", port=8123, reload=False)


if __name__ == "__main__":
    run()
