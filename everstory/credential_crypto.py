"""Envelope encryption for account-scoped player API credentials."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialEncryptionError(RuntimeError):
    """Raised when encrypted credentials cannot be safely stored or opened."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _derive_key(secret: str) -> bytes:
    if len(secret) < 32:
        raise CredentialEncryptionError(
            "BYOK master keys must contain at least 32 characters."
        )
    return hashlib.sha256(f"everstory-byok-v1:{secret}".encode()).digest()


class EnvelopeCipher:
    """AES-256-GCM data encryption with a separately wrapped random data key."""

    algorithm = "AES-256-GCM+ENVELOPE-v1"

    def __init__(
        self,
        active_key_id: str,
        active_secret: str,
        previous_secrets: dict[str, str] | None = None,
    ) -> None:
        if not active_key_id or len(active_key_id) > 80:
            raise CredentialEncryptionError("Invalid BYOK master key id.")
        secrets_by_id = dict(previous_secrets or {})
        secrets_by_id[active_key_id] = active_secret
        self.active_key_id = active_key_id
        self._master_keys = {
            key_id: _derive_key(secret)
            for key_id, secret in secrets_by_id.items()
        }

    @classmethod
    def from_env(cls) -> EnvelopeCipher | None:
        active_secret = os.getenv("BYOK_MASTER_KEY", "").strip()
        if not active_secret:
            return None
        active_key_id = os.getenv("BYOK_MASTER_KEY_ID", "local-v1").strip()
        raw_previous = os.getenv("BYOK_PREVIOUS_MASTER_KEYS", "{}").strip() or "{}"
        try:
            previous = json.loads(raw_previous)
        except json.JSONDecodeError as exc:
            raise CredentialEncryptionError(
                "BYOK_PREVIOUS_MASTER_KEYS must be a JSON object."
            ) from exc
        if not isinstance(previous, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in previous.items()
        ):
            raise CredentialEncryptionError(
                "BYOK_PREVIOUS_MASTER_KEYS must map key ids to secrets."
            )
        return cls(active_key_id, active_secret, previous)

    def encrypt_json(self, value: Any, associated_data: bytes) -> dict[str, str]:
        plaintext = json.dumps(
            value, ensure_ascii=False, separators=(",", ":")
        ).encode()
        data_key = secrets.token_bytes(32)
        payload_nonce = secrets.token_bytes(12)
        wrap_nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(data_key).encrypt(
            payload_nonce, plaintext, associated_data
        )
        wrapped_data_key = AESGCM(
            self._master_keys[self.active_key_id]
        ).encrypt(wrap_nonce, data_key, b"everstory-wrapped-key-v1:" + associated_data)
        return {
            "algorithm": self.algorithm,
            "key_id": self.active_key_id,
            "ciphertext": _encode(ciphertext),
            "payload_nonce": _encode(payload_nonce),
            "wrapped_data_key": _encode(wrapped_data_key),
            "wrap_nonce": _encode(wrap_nonce),
        }

    def decrypt_json(
        self, envelope: dict[str, str], associated_data: bytes
    ) -> Any:
        if envelope.get("algorithm") != self.algorithm:
            raise CredentialEncryptionError("Unsupported credential cipher.")
        key_id = str(envelope.get("key_id") or "")
        master_key = self._master_keys.get(key_id)
        if master_key is None:
            raise CredentialEncryptionError(
                f"Credential master key '{key_id}' is unavailable."
            )
        try:
            data_key = AESGCM(master_key).decrypt(
                _decode(envelope["wrap_nonce"]),
                _decode(envelope["wrapped_data_key"]),
                b"everstory-wrapped-key-v1:" + associated_data,
            )
            plaintext = AESGCM(data_key).decrypt(
                _decode(envelope["payload_nonce"]),
                _decode(envelope["ciphertext"]),
                associated_data,
            )
            return json.loads(plaintext)
        except (InvalidTag, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise CredentialEncryptionError(
                "Encrypted credentials failed integrity verification."
            ) from exc
