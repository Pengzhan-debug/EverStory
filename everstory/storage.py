"""Durable runtime and save-game storage backends.

The default backend deliberately keeps the original zero-configuration file
save behaviour.  Setting ``DATABASE_URL`` switches the API to PostgreSQL (or
SQLite in tests) without changing the HTTP contract.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from . import persistence
from .engine import WorldSession


JsonDocument = JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_database_url(database_url: str) -> str:
    """Select the installed psycopg 3 driver for common hosted Postgres URLs."""
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="guest", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerSession(Base):
    __tablename__ = "player_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    runtime_payload: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True
    )


class SaveGame(Base):
    __tablename__ = "save_games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("player_sessions.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    turn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class UsageEvent(Base):
    __tablename__ = "llm_usage_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("player_sessions.id"), index=True
    )
    agent: Mapped[str] = mapped_column(String(80), default="unassigned")
    model: Mapped[str] = mapped_column(String(160), default="")
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class FileStorage:
    """Original local save behaviour plus a no-op runtime store."""

    name = "file"
    durable_runtime = False

    def _root(self, session_id: str) -> Path:
        return Path(persistence.SAVES_DIR) / session_id

    def load_runtime(self, session_id: str) -> dict[str, Any] | None:
        return None

    def save_runtime(self, session_id: str, payload: dict[str, Any]) -> None:
        return None

    def save_game(
        self, session_id: str, name: str, world: WorldSession, extra: dict[str, Any]
    ) -> str:
        return str(
            persistence.save_session(world, name, saves_dir=self._root(session_id), extra=extra)
        )

    def list_games(self, session_id: str) -> list[dict[str, Any]]:
        return persistence.list_saves(self._root(session_id))

    def load_game(
        self, session_id: str, reference: str
    ) -> tuple[WorldSession, dict[str, Any]]:
        path = Path(reference).resolve()
        root = self._root(session_id).resolve()
        if not path.is_relative_to(root) or not path.exists():
            raise ValueError("invalid save path")
        return persistence.load_session_bundle(path)

    def sync_usage(self, session_id: str, calls: list[dict[str, Any]]) -> None:
        return None

    def load_usage(self, session_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        return []

    def health(self) -> dict[str, Any]:
        return {"backend": self.name, "ok": True, "durable_runtime": False}


class DatabaseStorage:
    """SQLAlchemy-backed authoritative storage for PostgreSQL deployments."""

    name = "postgresql"
    durable_runtime = True

    def __init__(self, database_url: str, *, create_schema: bool = True):
        database_url = normalize_database_url(database_url)
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            self.name = "sqlite"
        self.engine = create_engine(database_url, **kwargs)
        if create_schema:
            Base.metadata.create_all(self.engine)

    def _ensure_session(self, db: Session, session_id: str) -> PlayerSession:
        player_session = db.get(PlayerSession, session_id)
        if player_session is not None:
            return player_session
        if db.get(User, session_id) is None:
            db.add(User(id=session_id, kind="guest"))
        player_session = PlayerSession(id=session_id, user_id=session_id)
        db.add(player_session)
        db.flush()
        return player_session

    def load_runtime(self, session_id: str) -> dict[str, Any] | None:
        with Session(self.engine) as db:
            row = db.get(PlayerSession, session_id)
            return dict(row.runtime_payload) if row and row.runtime_payload else None

    def save_runtime(self, session_id: str, payload: dict[str, Any]) -> None:
        with Session(self.engine) as db, db.begin():
            row = self._ensure_session(db, session_id)
            row.runtime_payload = payload
            row.updated_at = utcnow()

    def save_game(
        self, session_id: str, name: str, world: WorldSession, extra: dict[str, Any]
    ) -> str:
        payload = persistence.session_to_dict(world, extra=extra)
        save_id = uuid.uuid4().hex
        evidence_count = len(extra.get("team_chat", {}).get("evidence", []))
        with Session(self.engine) as db, db.begin():
            self._ensure_session(db, session_id)
            db.add(
                SaveGame(
                    id=save_id,
                    session_id=session_id,
                    name=name[:120],
                    title=world.title[:200],
                    turn=world.state.turn,
                    evidence_count=evidence_count,
                    payload=payload,
                )
            )
        return f"db:{save_id}"

    def list_games(self, session_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(SaveGame)
                .where(SaveGame.session_id == session_id)
                .order_by(SaveGame.created_at.desc())
            ).all()
            return [
                {
                    "name": row.name,
                    "path": f"db:{row.id}",
                    "turn": row.turn,
                    "title": row.title,
                    "saved_at": row.created_at.isoformat(),
                    "evidence": row.evidence_count,
                }
                for row in rows
            ]

    def load_game(
        self, session_id: str, reference: str
    ) -> tuple[WorldSession, dict[str, Any]]:
        if not reference.startswith("db:"):
            raise ValueError("invalid save path")
        with Session(self.engine) as db:
            row = db.get(SaveGame, reference[3:])
            if row is None or row.session_id != session_id:
                raise ValueError("invalid save path")
            payload = dict(row.payload)
        extra = payload.get("extra")
        return persistence.session_from_dict(payload), extra if isinstance(extra, dict) else {}

    def sync_usage(self, session_id: str, calls: list[dict[str, Any]]) -> None:
        if not calls:
            return
        with Session(self.engine) as db, db.begin():
            self._ensure_session(db, session_id)
            ids = [str(call.get("id") or "") for call in calls if call.get("id")]
            existing = set(
                db.scalars(select(UsageEvent.id).where(UsageEvent.id.in_(ids))).all()
            ) if ids else set()
            for call in calls:
                call_id = str(call.get("id") or "")
                if not call_id or call_id in existing:
                    continue
                created_at = call.get("created_at")
                try:
                    timestamp = datetime.fromisoformat(str(created_at))
                except (TypeError, ValueError):
                    timestamp = utcnow()
                db.add(
                    UsageEvent(
                        id=call_id,
                        session_id=session_id,
                        agent=str(call.get("agent") or "unassigned")[:80],
                        model=str(call.get("model") or "")[:160],
                        total_tokens=int(call.get("total_tokens") or 0),
                        payload=call,
                        created_at=timestamp,
                    )
                )

    def load_usage(self, session_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(UsageEvent)
                .where(UsageEvent.session_id == session_id)
                .order_by(UsageEvent.created_at.desc())
                .limit(limit)
            ).all()
            return [dict(row.payload) for row in reversed(rows)]

    def health(self) -> dict[str, Any]:
        try:
            with Session(self.engine) as db:
                db.execute(select(1))
            return {"backend": self.name, "ok": True, "durable_runtime": True}
        except Exception as exc:  # pragma: no cover - depends on external service
            return {
                "backend": self.name,
                "ok": False,
                "durable_runtime": True,
                "error": str(exc)[:160],
            }


def build_storage() -> FileStorage | DatabaseStorage:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return FileStorage()
    create_schema = os.getenv("DATABASE_AUTO_CREATE", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    return DatabaseStorage(database_url, create_schema=create_schema)
