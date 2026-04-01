from __future__ import annotations

import tempfile
import unittest

from aws_local_audit.security import EvidenceVault, KeyringSecretStore


class SecurityTests(unittest.TestCase):
    def test_file_secret_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = KeyringSecretStore(namespace="test_grc", file_dir=tmp)
            provider = store.set_secret("sample", "value-123")
            self.assertIn(provider, {"keyring", "file"})
            self.assertTrue(store.has_secret("sample"))
            self.assertEqual(store.get_secret("sample"), "value-123")
            store.delete_secret("sample")
            self.assertFalse(store.has_secret("sample"))

    def test_evidence_vault_encrypts_and_decrypts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = KeyringSecretStore(namespace="test_grc", file_dir=tmp)
            vault = EvidenceVault(store)
            payload = {"control": "A.8.15", "status": "pass"}
            encrypted = vault.encrypt_json(payload)
            self.assertNotIn('"status": "pass"', encrypted)
            self.assertEqual(vault.decrypt_json(encrypted), payload)


if __name__ == "__main__":
    unittest.main()
