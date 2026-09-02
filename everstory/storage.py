"""Durable runtime and save-game storage backends.

The default backend deliberately keeps the original zero-configuration file
save behaviour.  Setting ``DATABASE_URL`` switches the API to PostgreSQL (or
SQLite in tests) without changing the HTTP contract.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    create_engine,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from . import persistence
from .engine import WorldSession


JsonDocument = JSON().with_variant(JSONB, "postgresql")
_PROCESS_CHALLENGE_SECRET = secrets.token_bytes(32)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_database_url(database_url: str) -> str:
    """Select the installed psycopg 3 driver for common hosted Postgres URLs."""
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("invalid email address")
    return email


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def challenge_digest(secret: bytes, challenge_id: str, code: str) -> str:
    return hmac.new(
        secret, f"{challenge_id}:{code}".encode(), hashlib.sha256
    ).hexdigest()


@dataclass(frozen=True)
class IdentityContext:
    user_id: str
    runtime_id: str
    kind: str = "guest"
    auth_session_id: str = ""
    email: str = ""
    display_name: str = ""
    runtime_replaced: bool = False
    replacement_auth_token: str = ""
    replacement_csrf_token: str = ""


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="guest", nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LoginChallenge(Base):
    __tablename__ = "login_challenges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


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
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
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
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
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

    def __init__(self):
        self._identity_lock = RLock()
        self._auth_sessions: dict[str, dict[str, Any]] = {}
        self._users: dict[str, dict[str, Any]] = {}
        self._challenges: dict[str, dict[str, Any]] = {}
        self._runtime_owners: dict[str, str] = {}
        configured_secret = os.getenv("AUTH_CHALLENGE_SECRET", "").encode()
        self._challenge_secret = configured_secret or _PROCESS_CHALLENGE_SECRET
        self.auth_ttl_seconds = max(
            60, int(os.getenv("SESSION_TTL_SECONDS", "2592000"))
        )

    def _issue_auth_locked(
        self, user_id: str
    ) -> tuple[str, str, dict[str, Any]]:
        now = utcnow()
        auth_token = secrets.token_hex(32)
        csrf_token = secrets.token_hex(32)
        record = {
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "csrf_hash": sha256_text(csrf_token),
            "created_at": now,
            "last_seen_at": now,
            "expires_at": now + timedelta(seconds=self.auth_ttl_seconds),
            "revoked_at": None,
        }
        self._auth_sessions[sha256_text(auth_token)] = record
        return auth_token, csrf_token, record

    def _root(self, session_id: str) -> Path:
        return Path(persistence.SAVES_DIR) / session_id

    def resolve_identity(
        self,
        auth_token: str,
        runtime_id: str,
        legacy_session_id: str = "",
        csrf_token: str = "",
    ) -> IdentityContext:
        token_hash = sha256_text(auth_token)
        runtime_replaced = False
        replacement_auth_token = ""
        replacement_csrf_token = ""
        with self._identity_lock:
            now = utcnow()
            auth = self._auth_sessions.get(token_hash)
            auth_valid = bool(
                auth
                and auth["revoked_at"] is None
                and auth["expires_at"] > now
            )
            if not auth_valid:
                # Never accept a caller-chosen unknown token as an authority
                # credential.  The server issues the token that becomes valid.
                user_id = legacy_session_id or uuid.uuid4().hex
                self._users.setdefault(
                    user_id,
                    {"id": user_id, "kind": "guest", "email": "", "display_name": ""},
                )
                replacement_auth_token, replacement_csrf_token, auth = (
                    self._issue_auth_locked(user_id)
                )
            else:
                user_id = str(auth["user_id"])
                auth["last_seen_at"] = now
                if not csrf_token or not hmac.compare_digest(
                    str(auth["csrf_hash"]), sha256_text(csrf_token)
                ):
                    replacement_csrf_token = secrets.token_hex(32)
                    auth["csrf_hash"] = sha256_text(replacement_csrf_token)
            user = self._users.setdefault(
                user_id,
                {"id": user_id, "kind": "guest", "email": "", "display_name": ""},
            )
            owner = self._runtime_owners.get(runtime_id)
            if owner is not None and owner != user_id:
                runtime_id = uuid.uuid4().hex
                runtime_replaced = True
            self._runtime_owners[runtime_id] = user_id
        return IdentityContext(
            user_id=user_id,
            runtime_id=runtime_id,
            kind=str(user["kind"]),
            auth_session_id=str(auth["id"]),
            email=str(user.get("email") or ""),
            display_name=str(user.get("display_name") or ""),
            runtime_replaced=runtime_replaced,
            replacement_auth_token=replacement_auth_token,
            replacement_csrf_token=replacement_csrf_token,
        )

    def create_login_challenge(
        self, email: str, locale: str = "en"
    ) -> dict[str, Any]:
        normalized = normalize_email(email)
        challenge_id = uuid.uuid4().hex
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = utcnow()
        with self._identity_lock:
            self._challenges[challenge_id] = {
                "email_hash": sha256_text(normalized),
                "code_hash": challenge_digest(
                    self._challenge_secret, challenge_id, code
                ),
                "locale": "zh-CN" if locale == "zh-CN" else "en",
                "attempts": 0,
                "created_at": now,
                "expires_at": now + timedelta(minutes=10),
                "consumed_at": None,
            }
        return {"id": challenge_id, "code": code, "expires_in": 600}

    def verify_login_challenge(
        self,
        challenge_id: str,
        email: str,
        code: str,
        current_user_id: str,
        current_auth_session_id: str,
        runtime_id: str,
    ) -> IdentityContext:
        normalized = normalize_email(email)
        now = utcnow()
        with self._identity_lock:
            challenge = self._challenges.get(challenge_id)
            if (
                challenge is None
                or challenge["consumed_at"] is not None
                or challenge["expires_at"] <= now
                or challenge["attempts"] >= 5
                or not hmac.compare_digest(
                    str(challenge["email_hash"]), sha256_text(normalized)
                )
            ):
                raise ValueError("invalid or expired verification challenge")
            challenge["attempts"] += 1
            expected = challenge_digest(self._challenge_secret, challenge_id, code)
            if not hmac.compare_digest(str(challenge["code_hash"]), expected):
                raise ValueError("invalid or expired verification challenge")
            challenge["consumed_at"] = now

            current = self._users[current_user_id]
            target = next(
                (
                    user
                    for user in self._users.values()
                    if user.get("kind") == "registered"
                    and user.get("email") == normalized
                ),
                None,
            )
            if target is None:
                target = current
                target["kind"] = "registered"
                target["email"] = normalized
                target["display_name"] = normalized.split("@", 1)[0][:80]
            elif target["id"] != current_user_id and current["kind"] == "guest":
                for owned_runtime, owner in list(self._runtime_owners.items()):
                    if owner == current_user_id:
                        self._runtime_owners[owned_runtime] = target["id"]
                current["kind"] = "disabled"

            for record in self._auth_sessions.values():
                if record["id"] == current_auth_session_id or (
                    current["kind"] == "disabled"
                    and record["user_id"] == current_user_id
                ):
                    record["revoked_at"] = now

            target_id = str(target["id"])
            if self._runtime_owners.get(runtime_id) != target_id:
                runtime_id = uuid.uuid4().hex
                self._runtime_owners[runtime_id] = target_id
            auth_token, csrf_token, auth = self._issue_auth_locked(target_id)
            return IdentityContext(
                user_id=target_id,
                runtime_id=runtime_id,
                kind="registered",
                auth_session_id=str(auth["id"]),
                email=str(target.get("email") or ""),
                display_name=str(target.get("display_name") or ""),
                replacement_auth_token=auth_token,
                replacement_csrf_token=csrf_token,
            )

    def list_auth_sessions(
        self, user_id: str, current_auth_session_id: str
    ) -> list[dict[str, Any]]:
        with self._identity_lock:
            rows = [
                record
                for record in self._auth_sessions.values()
                if record["user_id"] == user_id and record["revoked_at"] is None
            ]
            rows.sort(key=lambda row: row["last_seen_at"], reverse=True)
            return [
                {
                    "id": row["id"],
                    "current": row["id"] == current_auth_session_id,
                    "created_at": row["created_at"].isoformat(),
                    "last_seen_at": row["last_seen_at"].isoformat(),
                    "expires_at": row["expires_at"].isoformat(),
                }
                for row in rows
            ]

    def revoke_auth_session(
        self, user_id: str, auth_session_id: str
    ) -> bool:
        with self._identity_lock:
            for record in self._auth_sessions.values():
                if record["id"] == auth_session_id and record["user_id"] == user_id:
                    record["revoked_at"] = utcnow()
                    return True
        return False

    def load_runtime(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        return None

    def save_runtime(
        self, user_id: str, session_id: str, payload: dict[str, Any]
    ) -> None:
        return None

    def save_game(
        self,
        user_id: str,
        session_id: str,
        name: str,
        world: WorldSession,
        extra: dict[str, Any],
    ) -> str:
        return str(
            persistence.save_session(
                world, name, saves_dir=self._root(session_id), extra=extra
            )
        )

    def list_games(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        return persistence.list_saves(self._root(session_id))

    def load_game(
        self, user_id: str, session_id: str, reference: str
    ) -> tuple[WorldSession, dict[str, Any]]:
        path = Path(reference).resolve()
        root = self._root(session_id).resolve()
        if not path.is_relative_to(root) or not path.exists():
            raise ValueError("invalid save path")
        return persistence.load_session_bundle(path)

    def sync_usage(
        self, user_id: str, session_id: str, calls: list[dict[str, Any]]
    ) -> None:
        return None

    def load_usage(
        self, user_id: str, session_id: str, limit: int = 2000
    ) -> list[dict[str, Any]]:
        return []

    def health(self) -> dict[str, Any]:
        return {"backend": self.name, "ok": True, "durable_runtime": False}


class DatabaseStorage:
    """SQLAlchemy-backed authoritative storage for PostgreSQL deployments."""

    name = "postgresql"
    durable_runtime = True

    def __init__(self, database_url: str, *, create_schema: bool = True):
        database_url = normalize_database_url(database_url)
        self.auth_ttl_seconds = max(
            60, int(os.getenv("SESSION_TTL_SECONDS", "2592000"))
        )
        configured_secret = os.getenv("AUTH_CHALLENGE_SECRET", "").encode()
        self._challenge_secret = configured_secret or _PROCESS_CHALLENGE_SECRET
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            self.name = "sqlite"
        self.engine = create_engine(database_url, **kwargs)
        if create_schema:
            Base.metadata.create_all(self.engine)

    def _ensure_user(self, db: Session, user_id: str) -> User:
        user = db.get(User, user_id)
        if user is None:
            user = User(id=user_id, kind="guest")
            db.add(user)
            db.flush()
        return user

    def _ensure_session(
        self, db: Session, user_id: str, session_id: str
    ) -> PlayerSession:
        player_session = db.scalar(
            select(PlayerSession).where(
                PlayerSession.id == session_id,
                PlayerSession.user_id == user_id,
            )
        )
        if player_session is not None:
            return player_session
        if db.get(PlayerSession, session_id) is not None:
            raise PermissionError("runtime belongs to another user")
        self._ensure_user(db, user_id)
        player_session = PlayerSession(id=session_id, user_id=user_id)
        db.add(player_session)
        db.flush()
        return player_session

    def _issue_auth(
        self, db: Session, user_id: str, now: datetime
    ) -> tuple[str, str, AuthSession]:
        auth_token = secrets.token_hex(32)
        csrf_token = secrets.token_hex(32)
        auth = AuthSession(
            id=uuid.uuid4().hex,
            user_id=user_id,
            token_hash=sha256_text(auth_token),
            csrf_hash=sha256_text(csrf_token),
            expires_at=now + timedelta(seconds=self.auth_ttl_seconds),
        )
        db.add(auth)
        db.flush()
        return auth_token, csrf_token, auth

    def resolve_identity(
        self,
        auth_token: str,
        runtime_id: str,
        legacy_session_id: str = "",
        csrf_token: str = "",
    ) -> IdentityContext:
        token_hash = sha256_text(auth_token)
        now = utcnow()
        runtime_replaced = False
        replacement_auth_token = ""
        replacement_csrf_token = ""
        with Session(self.engine) as db, db.begin():
            auth = db.scalar(
                select(AuthSession).where(AuthSession.token_hash == token_hash)
            )
            auth_expires = auth.expires_at if auth is not None else None
            if auth_expires is not None and auth_expires.tzinfo is None:
                auth_expires = auth_expires.replace(tzinfo=timezone.utc)
            auth_is_valid = bool(
                auth is not None
                and auth.revoked_at is None
                and auth_expires is not None
                and auth_expires > now
            )
            if auth is None or not auth_is_valid:
                # Unknown tokens may be attacker-selected (session fixation),
                # so both missing and expired credentials receive a new
                # server-generated secret before they are persisted.
                replacement_auth_token = secrets.token_hex(32)
                replacement_csrf_token = secrets.token_hex(32)
                token_hash = sha256_text(replacement_auth_token)
                if auth is not None:
                    if auth.revoked_at is None:
                        auth.revoked_at = now
                legacy_user = (
                    db.get(User, legacy_session_id) if legacy_session_id else None
                )
                user = legacy_user or User(id=uuid.uuid4().hex, kind="guest")
                if legacy_user is None:
                    db.add(user)
                    db.flush()
                auth = AuthSession(
                    id=uuid.uuid4().hex,
                    user_id=user.id,
                    token_hash=token_hash,
                    csrf_hash=sha256_text(replacement_csrf_token),
                    expires_at=now + timedelta(seconds=self.auth_ttl_seconds),
                )
                db.add(auth)
            else:
                user = db.get(User, auth.user_id)
                auth.last_seen_at = now
                if not csrf_token or not hmac.compare_digest(
                    auth.csrf_hash, sha256_text(csrf_token)
                ):
                    replacement_csrf_token = secrets.token_hex(32)
                    auth.csrf_hash = sha256_text(replacement_csrf_token)
            user.last_seen_at = now

            player_session = db.get(PlayerSession, runtime_id)
            if player_session is not None and player_session.user_id != user.id:
                runtime_id = uuid.uuid4().hex
                player_session = None
                runtime_replaced = True
            if player_session is None:
                db.add(PlayerSession(id=runtime_id, user_id=user.id))

            return IdentityContext(
                user_id=user.id,
                runtime_id=runtime_id,
                kind=user.kind,
                auth_session_id=auth.id,
                email=user.email or "",
                display_name=user.display_name or "",
                runtime_replaced=runtime_replaced,
                replacement_auth_token=replacement_auth_token,
                replacement_csrf_token=replacement_csrf_token,
            )

    def create_login_challenge(
        self, email: str, locale: str = "en"
    ) -> dict[str, Any]:
        normalized = normalize_email(email)
        challenge_id = uuid.uuid4().hex
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = utcnow()
        with Session(self.engine) as db, db.begin():
            db.add(
                LoginChallenge(
                    id=challenge_id,
                    email_hash=sha256_text(normalized),
                    code_hash=challenge_digest(
                        self._challenge_secret, challenge_id, code
                    ),
                    locale="zh-CN" if locale == "zh-CN" else "en",
                    expires_at=now + timedelta(minutes=10),
                )
            )
        return {"id": challenge_id, "code": code, "expires_in": 600}

    def verify_login_challenge(
        self,
        challenge_id: str,
        email: str,
        code: str,
        current_user_id: str,
        current_auth_session_id: str,
        runtime_id: str,
    ) -> IdentityContext:
        normalized = normalize_email(email)
        now = utcnow()
        identity: IdentityContext | None = None
        with Session(self.engine) as db, db.begin():
            challenge = db.scalar(
                select(LoginChallenge)
                .where(LoginChallenge.id == challenge_id)
                .with_for_update()
            )
            expires_at = challenge.expires_at if challenge is not None else None
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if (
                challenge is None
                or challenge.consumed_at is not None
                or expires_at is None
                or expires_at <= now
                or challenge.attempts >= 5
                or not hmac.compare_digest(
                    challenge.email_hash, sha256_text(normalized)
                )
            ):
                raise ValueError("invalid or expired verification challenge")
            challenge.attempts += 1
            expected = challenge_digest(self._challenge_secret, challenge_id, code)
            if hmac.compare_digest(challenge.code_hash, expected):
                challenge.consumed_at = now

                current = db.get(User, current_user_id)
                if current is None or current.kind == "disabled":
                    raise ValueError("current user is unavailable")
                target = db.scalar(select(User).where(User.email == normalized))
                if target is None:
                    target = current
                    target.kind = "registered"
                    target.email = normalized
                    target.email_verified_at = now
                    if not target.display_name:
                        target.display_name = normalized.split("@", 1)[0][:80]
                elif target.id != current.id and current.kind == "guest":
                    db.execute(
                        update(PlayerSession)
                        .where(PlayerSession.user_id == current.id)
                        .values(user_id=target.id)
                    )
                    db.execute(
                        update(SaveGame)
                        .where(SaveGame.user_id == current.id)
                        .values(user_id=target.id)
                    )
                    db.execute(
                        update(UsageEvent)
                        .where(UsageEvent.user_id == current.id)
                        .values(user_id=target.id)
                    )
                    db.execute(
                        update(AuthSession)
                        .where(
                            AuthSession.user_id == current.id,
                            AuthSession.revoked_at.is_(None),
                        )
                        .values(revoked_at=now)
                    )
                    current.kind = "disabled"

                current_auth = db.get(AuthSession, current_auth_session_id)
                if current_auth is not None and current_auth.revoked_at is None:
                    current_auth.revoked_at = now

                player_session = db.get(PlayerSession, runtime_id)
                if player_session is None or player_session.user_id != target.id:
                    runtime_id = uuid.uuid4().hex
                    db.add(PlayerSession(id=runtime_id, user_id=target.id))

                auth_token, csrf_token, auth = self._issue_auth(db, target.id, now)
                target.last_seen_at = now
                identity = IdentityContext(
                    user_id=target.id,
                    runtime_id=runtime_id,
                    kind="registered",
                    auth_session_id=auth.id,
                    email=target.email or "",
                    display_name=target.display_name or "",
                    replacement_auth_token=auth_token,
                    replacement_csrf_token=csrf_token,
                )

        if identity is None:
            # Raise only after the transaction commits the failed attempt count.
            raise ValueError("invalid or expired verification challenge")
        return identity

    def list_auth_sessions(
        self, user_id: str, current_auth_session_id: str
    ) -> list[dict[str, Any]]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                )
                .order_by(AuthSession.last_seen_at.desc())
            ).all()
            return [
                {
                    "id": row.id,
                    "current": row.id == current_auth_session_id,
                    "created_at": row.created_at.isoformat(),
                    "last_seen_at": row.last_seen_at.isoformat(),
                    "expires_at": row.expires_at.isoformat(),
                }
                for row in rows
            ]

    def revoke_auth_session(
        self, user_id: str, auth_session_id: str
    ) -> bool:
        with Session(self.engine) as db, db.begin():
            auth = db.scalar(
                select(AuthSession).where(
                    AuthSession.id == auth_session_id,
                    AuthSession.user_id == user_id,
                )
            )
            if auth is None:
                return False
            if auth.revoked_at is None:
                auth.revoked_at = utcnow()
            return True

    def load_runtime(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with Session(self.engine) as db:
            row = db.scalar(
                select(PlayerSession).where(
                    PlayerSession.id == session_id,
                    PlayerSession.user_id == user_id,
                )
            )
            return dict(row.runtime_payload) if row and row.runtime_payload else None

    def save_runtime(
        self, user_id: str, session_id: str, payload: dict[str, Any]
    ) -> None:
        with Session(self.engine) as db, db.begin():
            row = self._ensure_session(db, user_id, session_id)
            row.runtime_payload = payload
            row.updated_at = utcnow()

    def save_game(
        self,
        user_id: str,
        session_id: str,
        name: str,
        world: WorldSession,
        extra: dict[str, Any],
    ) -> str:
        payload = persistence.session_to_dict(world, extra=extra)
        save_id = uuid.uuid4().hex
        evidence_count = len(extra.get("team_chat", {}).get("evidence", []))
        with Session(self.engine) as db, db.begin():
            self._ensure_session(db, user_id, session_id)
            db.add(
                SaveGame(
                    id=save_id,
                    user_id=user_id,
                    session_id=session_id,
                    name=name[:120],
                    title=world.title[:200],
                    turn=world.state.turn,
                    evidence_count=evidence_count,
                    payload=payload,
                )
            )
        return f"db:{save_id}"

    def list_games(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(SaveGame)
                .where(
                    SaveGame.user_id == user_id,
                    SaveGame.session_id == session_id,
                )
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
        self, user_id: str, session_id: str, reference: str
    ) -> tuple[WorldSession, dict[str, Any]]:
        if not reference.startswith("db:"):
            raise ValueError("invalid save path")
        with Session(self.engine) as db:
            row = db.get(SaveGame, reference[3:])
            if (
                row is None
                or row.user_id != user_id
                or row.session_id != session_id
            ):
                raise ValueError("invalid save path")
            payload = dict(row.payload)
        extra = payload.get("extra")
        return persistence.session_from_dict(payload), extra if isinstance(extra, dict) else {}

    def sync_usage(
        self, user_id: str, session_id: str, calls: list[dict[str, Any]]
    ) -> None:
        if not calls:
            return
        with Session(self.engine) as db, db.begin():
            self._ensure_session(db, user_id, session_id)
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
                        user_id=user_id,
                        session_id=session_id,
                        agent=str(call.get("agent") or "unassigned")[:80],
                        model=str(call.get("model") or "")[:160],
                        total_tokens=int(call.get("total_tokens") or 0),
                        payload=call,
                        created_at=timestamp,
                    )
                )

    def load_usage(
        self, user_id: str, session_id: str, limit: int = 2000
    ) -> list[dict[str, Any]]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(UsageEvent)
                .where(
                    UsageEvent.user_id == user_id,
                    UsageEvent.session_id == session_id,
                )
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
