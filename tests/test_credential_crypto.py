import unittest

from everstory.credential_crypto import (
    CredentialEncryptionError,
    EnvelopeCipher,
)


class EnvelopeCipherTests(unittest.TestCase):
    def test_round_trip_uses_random_ciphertext(self):
        cipher = EnvelopeCipher("test-v1", "a" * 64)
        value = {"private": {"api_key": "player-secret-123"}}

        first = cipher.encrypt_json(value, b"user:a")
        second = cipher.encrypt_json(value, b"user:a")

        self.assertEqual(cipher.decrypt_json(first, b"user:a"), value)
        self.assertNotEqual(first["ciphertext"], second["ciphertext"])
        self.assertNotIn("player-secret-123", str(first))

    def test_integrity_and_account_binding_are_enforced(self):
        cipher = EnvelopeCipher("test-v1", "b" * 64)
        envelope = cipher.encrypt_json({"api_key": "secret"}, b"user:a")

        with self.assertRaises(CredentialEncryptionError):
            cipher.decrypt_json(envelope, b"user:b")
        tampered = dict(envelope)
        tampered["ciphertext"] = tampered["ciphertext"][:-2] + "AA"
        with self.assertRaises(CredentialEncryptionError):
            cipher.decrypt_json(tampered, b"user:a")

    def test_previous_master_key_supports_rotation_and_rewrap(self):
        old = EnvelopeCipher("old-v1", "c" * 64)
        envelope = old.encrypt_json({"api_key": "secret"}, b"user:a")
        rotated = EnvelopeCipher(
            "new-v2", "d" * 64, previous_secrets={"old-v1": "c" * 64}
        )

        value = rotated.decrypt_json(envelope, b"user:a")
        rewrapped = rotated.encrypt_json(value, b"user:a")

        self.assertEqual(value, {"api_key": "secret"})
        self.assertEqual(rewrapped["key_id"], "new-v2")


if __name__ == "__main__":
    unittest.main()
