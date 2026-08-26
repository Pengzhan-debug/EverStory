"""EverStory web API + static frontend."""

from __future__ import annotations

import json
import mimetypes
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware

from ..agents import TeamChatSession
from ..config import build_client
from ..engine import WorldSession
from ..models import Action
from .. import persistence
from ..llm.settings import client_payload, update_client
from ..pipeline import TurnPipeline
from ..worlds import load_world

STATIC_DIR = Path(__file__).parent / "static"

# Some Windows MIME registries do not include WebP. Register it explicitly so
# StaticFiles returns a portable content type in local and packaged builds.
mimetypes.add_type("image/webp", ".webp")

SESSION_COOKIE = "everstory_session"
SESSION_ID_RE = re.compile(r"^[a-f0-9]{32}$")
MAX_RUNTIME_SESSIONS = 128


@dataclass
class RuntimeSlot:
    session: WorldSession
    pipeline: TurnPipeline
    team_chat: TeamChatSession = field(default_factory=TeamChatSession)
    lock: RLock = field(default_factory=RLock)
    touched_at: float = field(default_factory=time.monotonic)


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
            "attrs": {
                "locked": bool(e.attributes.get("locked", False)),
                "lit": bool(e.attributes.get("lit", False)),
                "filled": bool(e.attributes.get("filled", False)),
                "contains": len(e.attributes.get("contains", [])),
            },
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
    nearby_characters = [
        {"id": e.id, "name": e.name, "description": e.description}
        for e in st.entities.values()
        if e.kind.value == "character"
        and e.id != actor_id
        and e.location_id == actor.location_id
    ]
    nearby_items = [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "locked": bool(e.attributes.get("locked", False)),
        }
        for e in st.entities.values()
        if e.kind.value == "item"
        and e.location_id == actor.location_id
        and e.owner_id is None
    ]
    exits = [
        {"id": exit_id, "name": st.entity(exit_id).name}
        for exit_id in loc.attributes.get("connections", [])
        if exit_id in st.entities
    ]
    suggestions = [{"label": "Look around", "command": "look"}]
    suggestions.extend(
        {
            "label": f"Talk to {character['name']}",
            "command": f"talk to {character['id']}",
        }
        for character in nearby_characters[:2]
    )
    suggestions.extend(
        {"label": f"Take {item['name']}", "command": f"take {item['id']}"}
        for item in nearby_items[:2]
        if not item["locked"]
    )
    suggestions.extend(
        {"label": f"Go to {exit_['name']}", "command": f"move to {exit_['id']}"}
        for exit_ in exits[:3]
    )
    active_quest = next((quest["name"] for quest in quests if not quest["done"]), None)
    if loc.id == "storm_shore" and st.turn == 0:
        active_quest = "Reach shelter and establish contact with the investigation team"
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
        "scene": {
            "location": {
                "id": loc.id,
                "name": loc.name,
                "description": loc.description,
            },
            "characters": nearby_characters,
            "items": nearby_items,
            "exits": exits,
            "suggestions": suggestions[:6],
            "objective": active_quest or "Follow the evidence",
        },
    }


def create_app() -> FastAPI:
    app = FastAPI(title="EverStory", version="1.0.0")
    app.add_middleware(GZipMiddleware, minimum_size=500)
    runtimes: dict[str, RuntimeSlot] = {}
    runtimes_lock = RLock()

    def new_slot(client=None) -> RuntimeSlot:
        session = WorldSession(load_world("lost_lighthouse"))
        return RuntimeSlot(
            session=session,
            pipeline=TurnPipeline(session, client or build_client()),
        )

    def slot_for(request: Request) -> RuntimeSlot:
        session_id = request.state.session_id
        with runtimes_lock:
            slot = runtimes.get(session_id)
            if slot is None:
                if len(runtimes) >= MAX_RUNTIME_SESSIONS:
                    oldest_id = min(runtimes, key=lambda key: runtimes[key].touched_at)
                    runtimes.pop(oldest_id, None)
                slot = new_slot()
                runtimes[session_id] = slot
            slot.touched_at = time.monotonic()
            return slot

    def saves_dir_for(request: Request) -> Path:
        return Path(persistence.SAVES_DIR) / request.state.session_id

    @app.middleware("http")
    async def isolate_world_session(request: Request, call_next):
        raw = request.cookies.get(SESSION_COOKIE, "")
        is_new = SESSION_ID_RE.fullmatch(raw) is None
        request.state.session_id = uuid.uuid4().hex if is_new else raw
        response = await call_next(request)
        if is_new:
            response.set_cookie(
                SESSION_COOKIE,
                request.state.session_id,
                max_age=60 * 60 * 24 * 30,
                httponly=True,
                samesite="lax",
                path="/",
            )
        return response

    @app.middleware("http")
    async def cache_static_images(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/img/"):
            response.headers.setdefault("Cache-Control", "public, max-age=86400")
        return response

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/settings")
    def settings_page():
        return FileResponse(STATIC_DIR / "settings.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/llm/settings")
    def get_llm_settings(request: Request):
        slot = slot_for(request)
        with slot.lock:
            return client_payload(slot.pipeline.client)

    @app.put("/api/llm/settings")
    async def put_llm_settings(request: Request):
        slot = slot_for(request)
        body = await request.json()
        try:
            with slot.lock:
                client = update_client(slot.pipeline.client, body)
                slot.pipeline.client = client
                return {"ok": True, "settings": client_payload(client)}
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.post("/api/llm/test")
    async def test_llm_connection(request: Request):
        slot = slot_for(request)
        body = await request.json()
        connection_id = str(body.get("connection_id") or "").strip()
        agent = str(body.get("agent") or "").strip()

        def test_locked():
            with slot.lock:
                client = slot.pipeline.client
                if connection_id and connection_id not in client.connections:
                    raise ValueError("Unknown connection.")
                route_id, _, _, model = client.resolve_route(
                    agent=agent or None,
                    connection_id=connection_id or None,
                )
                if client.mode == "stub":
                    return {
                        "ok": True,
                        "connection_id": route_id,
                        "agent": agent or None,
                        "model": model,
                        "latency_ms": 0,
                        "message": "Offline stub mode is ready.",
                    }
                started = time.perf_counter()
                client.chat(
                    [
                        {"role": "system", "content": "Reply with OK only."},
                        {"role": "user", "content": "Connection test"},
                    ],
                    model=model,
                    temperature=0,
                    agent=agent or None,
                    connection_id=connection_id or None,
                )
                return {
                    "ok": True,
                    "connection_id": route_id,
                    "agent": agent or None,
                    "model": model,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                    "usage": dict(client.last_usage),
                    "message": "Connection verified.",
                }

        try:
            return await run_in_threadpool(test_locked)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except Exception as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "ok": False,
                    "connection_id": connection_id,
                    "agent": agent or None,
                    "error": str(exc)[:300],
                },
            )

    @app.post("/api/reset")
    def reset(request: Request):
        with runtimes_lock:
            current = runtimes.get(request.state.session_id)
            client = current.pipeline.client if current else build_client()
            runtimes[request.state.session_id] = new_slot(client)
        return {"ok": True}

    @app.post("/api/save")
    async def save(request: Request):
        body = await request.json()
        name = (body.get("name") or "autosave").strip() or "autosave"
        slot = slot_for(request)

        def save_locked():
            with slot.lock:
                path = persistence.save_session(
                    slot.session,
                    name,
                    saves_dir=saves_dir_for(request),
                    extra={
                        "team_chat": slot.team_chat.to_dict(),
                        "pipeline": slot.pipeline.memory_payload(),
                    },
                )
                return path, slot.session.state.turn, len(slot.team_chat.evidence)

        path, turn, evidence_count = await run_in_threadpool(save_locked)
        return {
            "ok": True,
            "path": str(path),
            "turn": turn,
            "evidence": evidence_count,
        }

    @app.get("/api/saves")
    def saves(request: Request):
        return {"saves": persistence.list_saves(saves_dir_for(request))}

    @app.post("/api/load")
    async def load(request: Request):
        body = await request.json()
        raw = (body.get("path") or "").strip()
        if not raw:
            return JSONResponse(status_code=400, content={"error": "missing path"})
        path = Path(raw).resolve()
        root = saves_dir_for(request).resolve()
        if not path.is_relative_to(root) or not path.exists():
            return JSONResponse(status_code=400, content={"error": "invalid save path"})
        session, extra = await run_in_threadpool(persistence.load_session_bundle, path)
        team_chat = TeamChatSession.from_dict(extra.get("team_chat"))
        with runtimes_lock:
            current = runtimes.get(request.state.session_id)
            client = current.pipeline.client if current else build_client()
            pipeline = TurnPipeline(session, client)
            pipeline.restore_memory(extra.get("pipeline"))
            runtimes[request.state.session_id] = RuntimeSlot(
                session=session,
                pipeline=pipeline,
                team_chat=team_chat,
            )
        return world_payload(session)

    @app.get("/api/world")
    def world(request: Request):
        slot = slot_for(request)
        with slot.lock:
            return world_payload(slot.session)

    @app.get("/api/agents/chat")
    def agent_chat_history(request: Request):
        slot = slot_for(request)
        with slot.lock:
            return slot.team_chat.payload()

    @app.get("/api/conversation")
    def conversation_history(request: Request):
        slot = slot_for(request)
        with slot.lock:
            return {"messages": list(slot.pipeline.transcript)}

    @app.post("/api/agents/chat")
    async def agent_chat_post(request: Request):
        slot = slot_for(request)
        body = await request.json()
        text = str(body.get("text") or "").strip()
        locale = "zh-CN" if body.get("locale") == "zh-CN" else "en"
        if not text:
            return JSONResponse(status_code=400, content={"error": "empty message"})

        def discuss_locked():
            with slot.lock:
                actor = slot.session.player_id()
                context = slot.session.visible_summary(actor)
                view = world_payload(slot.session)
                return slot.team_chat.post(
                    text, context, view, slot.pipeline.client, locale=locale
                )

        try:
            return await run_in_threadpool(discuss_locked)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        except Exception as exc:
            return JSONResponse(
                status_code=502,
                content={"error": f"Team channel unavailable: {str(exc)[:240]}"},
            )

    @app.post("/api/agents/tasks/{task_id}/approve")
    async def agent_task_approve(task_id: str, request: Request):
        slot = slot_for(request)

        def approve_locked():
            with slot.lock:
                def execute(action_spec: dict):
                    result = slot.session.act(
                        Action(
                            action_spec["type"],
                            slot.session.player_id(),
                            dict(action_spec.get("params") or {}),
                        )
                    )
                    return (
                        {
                            "type": result.action.action_type,
                            "ok": result.ok,
                            "message": result.message,
                            "effects": list(result.effects),
                        },
                        world_payload(slot.session),
                    )

                return slot.team_chat.approve_task(
                    task_id, world_payload(slot.session), executor=execute
                )

        try:
            return await run_in_threadpool(approve_locked)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.post("/api/turn")
    async def turn(request: Request):
        slot = slot_for(request)
        body = await request.json()
        text = (body.get("text") or "").strip()
        locale = "zh-CN" if body.get("locale") == "zh-CN" else "en"
        if not text:
            with slot.lock:
                return {
                    "reply": "Say something.",
                    "world": world_payload(slot.session),
                    "events": [],
                }
        # Run the LLM pipeline off the event loop so one slow turn never
        # blocks health checks or other sessions.
        def process_locked():
            with slot.lock:
                result = slot.pipeline.process(text, locale=locale)
                return result, world_payload(slot.session)

        result, current_world = await run_in_threadpool(process_locked)
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
            "world": current_world,
        }

    @app.post("/api/turn/stream")
    async def turn_stream(request: Request):
        """SSE endpoint: yields text deltas, then a final done event."""
        slot = slot_for(request)
        body = await request.json()
        text = (body.get("text") or "").strip()
        locale = "zh-CN" if body.get("locale") == "zh-CN" else "en"
        if not text:
            return JSONResponse(status_code=400, content={"error": "empty text"})

        def gen():
            try:
                with slot.lock:
                    for ev in slot.pipeline.process_stream(
                        text, world_renderer=world_payload, locale=locale
                    ):
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except Exception as exc:  # surface errors to the client
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:300]}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    # Port 8123 avoids clashing with other local dev servers (e.g. AgentForge
    # uses 8000/8080).
    uvicorn.run("everstory.api.main:app", host="127.0.0.1", port=8123, reload=False)


if __name__ == "__main__":
    run()
