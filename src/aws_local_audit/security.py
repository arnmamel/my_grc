from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import keyring
    from keyring.errors import KeyringError
except ImportError:  # pragma: no cover - dependency-managed at install time
    keyring = None

    class KeyringError(Exception):
        pass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SECURITY_NAMESPACE = "my_grc"
MASTER_KEY_NAME = "evidence_master_key_v1"


class SecurityError(RuntimeError):
    pass


@dataclass(slots=True)
class EncryptedEnvelope:
    storage_mode: str
    key_ref: str
    nonce_b64: str
    ciphertext_b64: str
    digest_sha256: str


class KeyringSecretStore:
    def __init__(self, namespace: str = SECURITY_NAMESPACE, file_dir: str | None = None):
        self.namespace = namespace
        self.file_dir = file_dir or ""
        self.last_provider = "unknown"

    def set_secret(self, name: str, value: str) -> str:
        if self._try_set_keyring_secret(name, value):
            self.last_provider = "keyring"
            return self.last_provider
        if self._try_set_file_secret(name, value):
            self.last_provider = "file"
            return self.last_provider
        raise SecurityError(
            "Secure secret storage requires either a working OS keyring backend or a writable secret files directory."
        )

    def get_secret(self, name: str) -> str:
        keyring_value = self._try_get_keyring_secret(name)
        if keyring_value:
            self.last_provider = "keyring"
            return keyring_value
        file_value = self._try_get_file_secret(name)
        if file_value:
            self.last_provider = "file"
            return file_value
        raise SecurityError(f"Secret '{name}' was not found in the configured secure secret backends.")

    def delete_secret(self, name: str) -> None:
        if keyring is not None:
            try:
                keyring.delete_password(self.namespace, name)
            except Exception:
                pass
        path = self._file_secret_path(name)
        if path and path.exists():
            path.unlink(missing_ok=True)

    def has_secret(self, name: str) -> bool:
        if self._try_get_keyring_secret(name):
            return True
        return bool(self._try_get_file_secret(name))

    def external_ref(self, name: str) -> str:
        return f"{self.namespace}:{name}"

    def _try_set_keyring_secret(self, name: str, value: str) -> bool:
        if keyring is None:
            return False
        try:
            keyring.set_password(self.namespace, name, value)
            return True
        except KeyringError:
            return False

    def _try_get_keyring_secret(self, name: str) -> str:
        if keyring is None:
            return ""
        try:
            return keyring.get_password(self.namespace, name) or ""
        except KeyringError:
            return ""

    def _try_set_file_secret(self, name: str, value: str) -> bool:
        path = self._file_secret_path(name)
        if path is None:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True

    def _try_get_file_secret(self, name: str) -> str:
        path = self._file_secret_path(name)
        if path is None or not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def _file_secret_path(self, name: str) -> Path | None:
        if not self.file_dir:
            return None
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in name).strip("_")
        return Path(self.file_dir) / f"{self.namespace}__{safe_name}.secret"


class EvidenceVault:
    def __init__(self, secret_store: KeyringSecretStore | None = None):
        self.secret_store = secret_store or KeyringSecretStore()

    def initialize(self) -> str:
        self._get_or_create_master_key()
        return MASTER_KEY_NAME

    def encrypt_json(self, payload: Any) -> str:
        plaintext = json.dumps(payload, indent=2, default=str, sort_keys=True).encode("utf-8")
        key = self._get_or_create_master_key()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        envelope = EncryptedEnvelope(
            storage_mode="aesgcm_v1",
            key_ref=MASTER_KEY_NAME,
            nonce_b64=base64.b64encode(nonce).decode("ascii"),
            ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
            digest_sha256=hashlib.sha256(plaintext).hexdigest(),
        )
        return json.dumps(asdict(envelope), indent=2)

    def decrypt_json(self, payload: str) -> Any:
        envelope = json.loads(payload)
        storage_mode = envelope.get("storage_mode", "plaintext")
        if storage_mode == "plaintext":
            return json.loads(payload)
        if storage_mode != "aesgcm_v1":
            raise SecurityError(f"Unsupported evidence storage mode: {storage_mode}")

        key = self._get_or_create_master_key()
        nonce = base64.b64decode(envelope["nonce_b64"])
        ciphertext = base64.b64decode(envelope["ciphertext_b64"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        digest = hashlib.sha256(plaintext).hexdigest()
        if digest != envelope["digest_sha256"]:
            raise SecurityError("Evidence payload integrity verification failed.")
        return json.loads(plaintext.decode("utf-8"))

    def digest_for_payload(self, payload: Any) -> str:
        plaintext = json.dumps(payload, indent=2, default=str, sort_keys=True).encode("utf-8")
        return hashlib.sha256(plaintext).hexdigest()

    def _get_or_create_master_key(self) -> bytes:
        if self.secret_store.has_secret(MASTER_KEY_NAME):
            return base64.b64decode(self.secret_store.get_secret(MASTER_KEY_NAME))
        key = AESGCM.generate_key(bit_length=256)
        self.secret_store.set_secret(MASTER_KEY_NAME, base64.b64encode(key).decode("ascii"))
        return key
