"""EverStory web API + static frontend."""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
import secrets
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
from ..auth_email import deliver_login_code
from ..config import build_client
from ..engine import WorldSession
from ..models import Action
from .. import persistence
from ..llm.settings import client_payload, update_client
from ..llm.usage import usage_payload
from ..pipeline import TurnPipeline
from ..redis_runtime import RedisRuntime, build_redis_runtime
from ..storage import DatabaseStorage, FileStorage, build_storage, normalize_email
from ..worlds import load_world

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)

# Some Windows MIME registries do not include WebP. Register it explicitly so
# StaticFiles returns a portable content type in local and packaged builds.
mimetypes.add_type("image/webp", ".webp")

AUTH_COOKIE = "everstory_auth"
RUNTIME_COOKIE = "everstory_runtime"
CSRF_COOKIE = "everstory_csrf"
LEGACY_SESSION_COOKIE = "everstory_session"
# Backward-compatible import used by clients/tests; it now identifies a game
# runtime rather than an authenticated user.
SESSION_COOKIE = RUNTIME_COOKIE
SESSION_ID_RE = re.compile(r"^[a-f0-9]{32}$")
AUTH_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")
CSRF_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")
MAX_RUNTIME_SESSIONS = 128


@dataclass
class RuntimeSlot:
    user_id: str
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


def create_app(
    storage: FileStorage | DatabaseStorage | None = None,
    redis_runtime: RedisRuntime | None = None,
) -> FastAPI:
    app = FastAPI(title="EverStory", version="1.3.0")
    app.add_middleware(GZipMiddleware, minimum_size=500)
    storage = storage or build_storage()
    redis_runtime = redis_runtime or build_redis_runtime()
    app.state.storage = storage
    app.state.redis_runtime = redis_runtime
    runtimes: dict[str, RuntimeSlot] = {}
    runtimes_lock = RLock()

    def new_slot(user_id: str, client=None) -> RuntimeSlot:
        session = WorldSession(load_world("lost_lighthouse"))
        return RuntimeSlot(
            user_id=user_id,
            session=session,
            pipeline=TurnPipeline(session, client or build_client()),
        )

    def slot_document(slot: RuntimeSlot) -> dict:
        return persistence.session_to_dict(
            slot.session,
            extra={
                "team_chat": slot.team_chat.to_dict(),
                "pipeline": slot.pipeline.memory_payload(),
                # Metrics are durable, while API credentials are intentionally
                # never serialized into a runtime document.
                "usage": list(slot.pipeline.client.call_history),
            },
        )

    def restore_slot(document: dict, user_id: str, session_id: str) -> RuntimeSlot:
        session = persistence.session_from_dict(document)
        raw_extra = document.get("extra")
        extra = raw_extra if isinstance(raw_extra, dict) else {}
        client = build_client()
        usage = extra.get("usage") if isinstance(extra.get("usage"), list) else []
        if not usage:
            usage = storage.load_usage(user_id, session_id)
        client.call_history.extend(call for call in usage if isinstance(call, dict))
        pipeline = TurnPipeline(session, client)
        pipeline.restore_memory(extra.get("pipeline"))
        return RuntimeSlot(
            user_id=user_id,
            session=session,
            pipeline=pipeline,
            team_chat=TeamChatSession.from_dict(extra.get("team_chat")),
        )

    def persist_slot(session_id: str, slot: RuntimeSlot) -> None:
        storage.save_runtime(slot.user_id, session_id, slot_document(slot))
        storage.sync_usage(
            slot.user_id, session_id, list(slot.pipeline.client.call_history)
        )

    def slot_for(request: Request) -> RuntimeSlot:
        session_id = request.state.session_id
        user_id = request.state.user_id
        with runtimes_lock:
            slot = runtimes.get(session_id)
            if slot is not None and slot.user_id != user_id:
                # A runtime id can never be reused as an authority boundary.
                runtimes.pop(session_id, None)
                slot = None
            if slot is None:
                if len(runtimes) >= MAX_RUNTIME_SESSIONS:
                    oldest_id = min(runtimes, key=lambda key: runtimes[key].touched_at)
                    oldest = runtimes.pop(oldest_id, None)
                    if oldest is not None:
                        persist_slot(oldest_id, oldest)
                document = storage.load_runtime(user_id, session_id)
                slot = (
                    restore_slot(document, user_id, session_id)
                    if document
                    else new_slot(user_id)
                )
                runtimes[session_id] = slot
            slot.touched_at = time.monotonic()
            return slot

    @app.middleware("http")
    async def isolate_world_session(request: Request, call_next):
        # Health probes and immutable assets have no player authority and must
        # not create guest rows or update auth-session last-seen timestamps.
        if request.url.path == "/api/health" or request.url.path.startswith(
            "/static/"
        ):
            return await call_next(request)
        raw_auth = request.cookies.get(AUTH_COOKIE, "")
        raw_runtime = request.cookies.get(RUNTIME_COOKIE, "")
        raw_csrf = request.cookies.get(CSRF_COOKIE, "")
        raw_legacy = request.cookies.get(LEGACY_SESSION_COOKIE, "")
        is_new_auth = AUTH_TOKEN_RE.fullmatch(raw_auth) is None
        auth_token = secrets.token_hex(32) if is_new_auth else raw_auth
        legacy_id = raw_legacy if SESSION_ID_RE.fullmatch(raw_legacy) else ""
        is_new_runtime = SESSION_ID_RE.fullmatch(raw_runtime) is None
        requested_runtime = (
            raw_runtime
            if not is_new_runtime
            else legacy_id or uuid.uuid4().hex
        )
        identity = storage.resolve_identity(
            auth_token,
            requested_runtime,
            legacy_id if is_new_auth else "",
            raw_csrf if CSRF_TOKEN_RE.fullmatch(raw_csrf) else "",
        )
        if identity.replacement_auth_token:
            auth_token = identity.replacement_auth_token
            is_new_auth = True
        request.state.user_id = identity.user_id
        request.state.session_id = identity.runtime_id
        request.state.user_kind = identity.kind
        request.state.auth_session_id = identity.auth_session_id
        request.state.user_email = identity.email
        request.state.user_display_name = identity.display_name
        cookie_secure = (
            request.url.scheme == "https"
            or os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
        )

        def apply_identity_cookies(response):
            if getattr(request.state, "clear_identity_cookies", False):
                for cookie_name in (AUTH_COOKIE, RUNTIME_COOKIE, CSRF_COOKIE):
                    response.delete_cookie(cookie_name, path="/")
                return response
            auth_to_set = getattr(request.state, "auth_token_to_set", "")
            csrf_to_set = getattr(request.state, "csrf_token_to_set", "")
            runtime_to_set = getattr(request.state, "runtime_id_to_set", "")
            if auth_to_set or is_new_auth:
                response.set_cookie(
                    AUTH_COOKIE,
                    auth_to_set or auth_token,
                    max_age=redis_runtime.session_ttl,
                    httponly=True,
                    secure=cookie_secure,
                    samesite="lax",
                    path="/",
                )
            if csrf_to_set or identity.replacement_csrf_token:
                response.set_cookie(
                    CSRF_COOKIE,
                    csrf_to_set or identity.replacement_csrf_token,
                    max_age=redis_runtime.session_ttl,
                    httponly=False,
                    secure=cookie_secure,
                    samesite="strict",
                    path="/",
                )
            if runtime_to_set or is_new_runtime or identity.runtime_replaced:
                response.set_cookie(
                    RUNTIME_COOKIE,
                    runtime_to_set or identity.runtime_id,
                    max_age=redis_runtime.session_ttl,
                    httponly=True,
                    secure=cookie_secure,
                    samesite="lax",
                    path="/",
                )
            if legacy_id:
                response.delete_cookie(LEGACY_SESSION_COOKIE, path="/")
            return response

        redis_runtime.touch(request.state.session_id)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf_enforced = os.getenv("CSRF_ENFORCE", "true").lower() in {
                "1",
                "true",
                "yes",
            }
            csrf_header = request.headers.get("X-CSRF-Token", "")
            csrf_cookie_valid = bool(
                CSRF_TOKEN_RE.fullmatch(raw_csrf)
                and not identity.replacement_csrf_token
            )
            if csrf_enforced and (
                not csrf_cookie_valid
                or not secrets.compare_digest(csrf_header, raw_csrf)
            ):
                return apply_identity_cookies(
                    JSONResponse(
                        status_code=403,
                        content={"error": "CSRF verification failed."},
                    )
                )
            allowed, _ = redis_runtime.allow(request.state.session_id)
            if not allowed:
                return apply_identity_cookies(
                    JSONResponse(
                        status_code=429,
                        content={"error": "Too many requests. Retry after the rate window."},
                        headers={"Retry-After": str(redis_runtime.rate_window)},
                    )
                )
        response = await call_next(request)
        return apply_identity_cookies(response)

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
        database = storage.health()
        coordination = redis_runtime.health()
        ready = bool(database.get("ok")) and bool(coordination.get("ok"))
        payload = {
            "status": "ok" if ready else "degraded",
            "version": "1.3.0",
            "database": database,
            "coordination": coordination,
        }
        return payload if ready else JSONResponse(status_code=503, content=payload)

    @app.get("/api/auth/session")
    def auth_session(request: Request):
        return {
            "user": {
                "id": request.state.user_id,
                "kind": request.state.user_kind,
                "registered": request.state.user_kind == "registered",
                "email": request.state.user_email,
                "display_name": request.state.user_display_name,
            },
            "runtime_id": request.state.session_id,
            "csrf_protected": os.getenv("CSRF_ENFORCE", "true").lower()
            in {"1", "true", "yes"},
        }

    @app.post("/api/auth/email/request", status_code=202)
    async def request_email_code(request: Request):
        body = await request.json()
        try:
            email = normalize_email(str(body.get("email") or ""))
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        locale = "zh-CN" if body.get("locale") == "zh-CN" else "en"
        ip_address = request.client.host if request.client else "unknown"
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        limit = max(1, int(os.getenv("AUTH_REQUEST_LIMIT", "5")))
        window = max(60, int(os.getenv("AUTH_REQUEST_WINDOW_SECONDS", "600")))
        ip_allowed, _ = redis_runtime.allow_quota(
            f"auth:ip:{ip_hash}", limit, window
        )
        email_allowed, _ = redis_runtime.allow_quota(
            f"auth:email:{email_hash}", limit, window
        )
        if not ip_allowed or not email_allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many verification requests. Try again later."},
                headers={"Retry-After": str(window)},
            )

        challenge = storage.create_login_challenge(email, locale)
        try:
            expose_code = await run_in_threadpool(
                deliver_login_code, email, challenge["code"], locale
            )
        except Exception:
            logger.exception("Email verification delivery failed")
            return JSONResponse(
                status_code=503,
                content={"error": "Email delivery is temporarily unavailable."},
            )
        payload = {
            "ok": True,
            "challenge_id": challenge["id"],
            "expires_in": challenge["expires_in"],
            "message": "If the address can receive mail, a code has been sent.",
        }
        if expose_code:
            payload["development_code"] = challenge["code"]
        return payload

    @app.post("/api/auth/email/verify")
    async def verify_email_code(request: Request):
        body = await request.json()
        challenge_id = str(body.get("challenge_id") or "").strip()
        code = str(body.get("code") or "").strip()
        email = str(body.get("email") or "").strip()
        if not SESSION_ID_RE.fullmatch(challenge_id) or not re.fullmatch(
            r"\d{6}", code
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid or expired verification challenge."},
            )
        try:
            identity = storage.verify_login_challenge(
                challenge_id,
                email,
                code,
                request.state.user_id,
                request.state.auth_session_id,
                request.state.session_id,
            )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid or expired verification challenge."},
            )

        old_runtime_id = request.state.session_id
        with runtimes_lock:
            slot = runtimes.get(old_runtime_id)
            if slot is not None and identity.runtime_id == old_runtime_id:
                slot.user_id = identity.user_id
            elif identity.runtime_id != old_runtime_id:
                runtimes.pop(identity.runtime_id, None)
        request.state.user_id = identity.user_id
        request.state.session_id = identity.runtime_id
        request.state.user_kind = identity.kind
        request.state.auth_session_id = identity.auth_session_id
        request.state.user_email = identity.email
        request.state.user_display_name = identity.display_name
        request.state.auth_token_to_set = identity.replacement_auth_token
        request.state.csrf_token_to_set = identity.replacement_csrf_token
        request.state.runtime_id_to_set = identity.runtime_id
        return {
            "ok": True,
            "user": {
                "id": identity.user_id,
                "kind": identity.kind,
                "registered": True,
                "email": identity.email,
                "display_name": identity.display_name,
            },
            "runtime_id": identity.runtime_id,
        }

    @app.get("/api/auth/sessions")
    def auth_sessions(request: Request):
        return {
            "sessions": storage.list_auth_sessions(
                request.state.user_id, request.state.auth_session_id
            )
        }

    @app.get("/api/auth/investigations")
    def account_investigations(request: Request):
        if request.state.user_kind != "registered":
            return JSONResponse(
                status_code=403,
                content={"error": "A verified account is required."},
            )
        return {
            "investigations": storage.list_investigations(
                request.state.user_id, request.state.session_id
            )
        }

    @app.post("/api/auth/investigations/{runtime_id}/activate")
    async def activate_account_investigation(runtime_id: str, request: Request):
        if request.state.user_kind != "registered":
            return JSONResponse(
                status_code=403,
                content={"error": "A verified account is required."},
            )
        target_is_owned = SESSION_ID_RE.fullmatch(
            runtime_id
        ) and storage.owns_investigation(request.state.user_id, runtime_id)
        if not target_is_owned:
            return JSONResponse(
                status_code=404,
                content={"error": "Investigation not found."},
            )

        previous_runtime_id = request.state.session_id
        if runtime_id != previous_runtime_id:
            previous_slot = slot_for(request)

            def persist_previous() -> None:
                with previous_slot.lock:
                    persist_slot(previous_runtime_id, previous_slot)

            await run_in_threadpool(persist_previous)
            request.state.session_id = runtime_id
            request.state.runtime_id_to_set = runtime_id
            redis_runtime.touch(runtime_id)

        active_slot = slot_for(request)
        with active_slot.lock:
            active_world = world_payload(active_slot.session)
        return {
            "ok": True,
            "runtime_id": runtime_id,
            "world": active_world,
            "investigations": storage.list_investigations(
                request.state.user_id, runtime_id
            ),
        }

    @app.delete("/api/auth/sessions/{auth_session_id}")
    def revoke_auth_session(auth_session_id: str, request: Request):
        revoked = storage.revoke_auth_session(
            request.state.user_id, auth_session_id
        )
        if not revoked:
            return JSONResponse(status_code=404, content={"error": "Session not found."})
        if auth_session_id == request.state.auth_session_id:
            request.state.clear_identity_cookies = True
        return {
            "ok": True,
            "current_session_revoked": auth_session_id
            == request.state.auth_session_id,
        }

    @app.post("/api/auth/logout")
    def logout(request: Request):
        storage.revoke_auth_session(
            request.state.user_id, request.state.auth_session_id
        )
        request.state.clear_identity_cookies = True
        return {"ok": True}

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
                persist_slot(request.state.session_id, slot)
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
            result = await run_in_threadpool(test_locked)
            await run_in_threadpool(persist_slot, request.state.session_id, slot)
            return result
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

    @app.get("/api/llm/usage")
    def get_llm_usage(
        request: Request,
        range: str = "7d",
        metric: str = "tokens",
        group_by: str = "source",
    ):
        slot = slot_for(request)
        try:
            with slot.lock:
                return usage_payload(
                    slot.pipeline.client,
                    range_key=range,
                    metric=metric,
                    group_by=group_by,
                )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.post("/api/reset")
    def reset(request: Request):
        with runtimes_lock:
            current = runtimes.get(request.state.session_id)
            client = current.pipeline.client if current else build_client()
            slot = new_slot(request.state.user_id, client)
            runtimes[request.state.session_id] = slot
            persist_slot(request.state.session_id, slot)
        return {"ok": True}

    @app.post("/api/save")
    async def save(request: Request):
        body = await request.json()
        name = (body.get("name") or "autosave").strip() or "autosave"
        slot = slot_for(request)

        def save_locked():
            with redis_runtime.session_lock(request.state.session_id), slot.lock:
                extra = {
                    "team_chat": slot.team_chat.to_dict(),
                    "pipeline": slot.pipeline.memory_payload(),
                    "usage": list(slot.pipeline.client.call_history),
                }
                reference = storage.save_game(
                    request.state.user_id,
                    request.state.session_id,
                    name,
                    slot.session,
                    extra,
                )
                persist_slot(request.state.session_id, slot)
                return reference, slot.session.state.turn, len(slot.team_chat.evidence)

        path, turn, evidence_count = await run_in_threadpool(save_locked)
        return {
            "ok": True,
            "path": str(path),
            "turn": turn,
            "evidence": evidence_count,
        }

    @app.get("/api/saves")
    def saves(request: Request):
        return {
            "saves": storage.list_games(
                request.state.user_id, request.state.session_id
            )
        }

    @app.post("/api/load")
    async def load(request: Request):
        body = await request.json()
        raw = (body.get("path") or "").strip()
        if not raw:
            return JSONResponse(status_code=400, content={"error": "missing path"})
        try:
            session, extra = await run_in_threadpool(
                storage.load_game,
                request.state.user_id,
                request.state.session_id,
                raw,
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "invalid save path"})
        team_chat = TeamChatSession.from_dict(extra.get("team_chat"))
        with runtimes_lock:
            current = runtimes.get(request.state.session_id)
            client = current.pipeline.client if current else build_client()
            usage = extra.get("usage") if isinstance(extra.get("usage"), list) else []
            client.call_history.clear()
            client.call_history.extend(call for call in usage if isinstance(call, dict))
            pipeline = TurnPipeline(session, client)
            pipeline.restore_memory(extra.get("pipeline"))
            slot = RuntimeSlot(
                user_id=request.state.user_id,
                session=session,
                pipeline=pipeline,
                team_chat=team_chat,
            )
            runtimes[request.state.session_id] = slot
            persist_slot(request.state.session_id, slot)
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
            with redis_runtime.session_lock(request.state.session_id), slot.lock:
                actor = slot.session.player_id()
                context = slot.session.visible_summary(actor)
                view = world_payload(slot.session)
                result = slot.team_chat.post(
                    text, context, view, slot.pipeline.client, locale=locale
                )
                persist_slot(request.state.session_id, slot)
                return result

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
            with redis_runtime.session_lock(request.state.session_id), slot.lock:
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

                result = slot.team_chat.approve_task(
                    task_id, world_payload(slot.session), executor=execute
                )
                persist_slot(request.state.session_id, slot)
                return result

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
            with redis_runtime.session_lock(request.state.session_id), slot.lock:
                result = slot.pipeline.process(text, locale=locale)
                current_world = world_payload(slot.session)
                persist_slot(request.state.session_id, slot)
                return result, current_world

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
                with redis_runtime.session_lock(request.state.session_id), slot.lock:
                    for ev in slot.pipeline.process_stream(
                        text, world_renderer=world_payload, locale=locale
                    ):
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    persist_slot(request.state.session_id, slot)
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
