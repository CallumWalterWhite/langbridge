import base64
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional, Any

from config import settings
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import constant_time
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag
import secrets


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii")

def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode("ascii"))

@dataclass(frozen=True)
class CipherRecord:
    """What you store in the DB (as JSON in a TEXT column, or separate columns if you prefer)."""
    alg: str         # "AES-256-GCM"
    kid: str         # key id / version, e.g., "v3"
    n: str           # nonce (b64)
    ct: str          # ciphertext+tag (b64)  (AESGCM appends tag to the end of ct)
    aad: Optional[str] = None  # optional AAD b64 (so you can reconstruct/decrypt deterministically)

    def to_json(self) -> str:
        return json.dumps({
            "alg": self.alg,
            "kid": self.kid,
            "n": self.n,
            "ct": self.ct,
            **({"aad": self.aad} if self.aad is not None else {})
        })

    @staticmethod
    def from_json(s: str) -> "CipherRecord":
        obj = json.loads(s)
        return CipherRecord(
            alg=obj["alg"],
            kid=obj["kid"],
            n=obj["n"],
            ct=obj["ct"],
            aad=obj.get("aad")
        )


# ------------------------------
# Keyring & Crypto
# ------------------------------

class Keyring:
    """
    Versioned keyring with a current (active) key used for encryption and
    historical keys kept to decrypt old rows.

    You can populate this from env or a secret manager.
    Example env JSON:
      CONFIG_KEYRING='{"v1":"<b64key1>","v2":"<b64key2>"}'
      CONFIG_ACTIVE_KEY="v2"
    """
    def __init__(self, keys: Dict[str, bytes], active_kid: str):
        if active_kid not in keys:
            raise ValueError("active_kid not found in keys")
        # Validate key sizes
        for kid, k in keys.items():
            if len(k) != 32:
                raise ValueError(f"Key {kid} must be 32 bytes for AES-256")
        self._keys = keys
        self._active_kid = active_kid

    @staticmethod
    def from_env(
    ) -> "Keyring":
        ring_json = settings.CONFIG_KEYRING
        active_kid = settings.CONFIG_ACTIVE_KEY
        if not ring_json or not active_kid:
            raise ValueError("CONFIG_KEYRING and CONFIG_ACTIVE_KEY must be set in env")
        raw = json.loads(ring_json)
        keys = {kid: b64d(b64key) for kid, b64key in raw.items()}
        return Keyring(keys, active_kid)

    @property
    def active(self) -> tuple[str, bytes]:
        return self._active_kid, self._keys[self._active_kid]

    def get(self, kid: str) -> Optional[bytes]:
        return self._keys.get(kid)

    def kids(self):
        return list(self._keys.keys())


class ConfigCrypto:
    """
    High-level API for encrypting/decrypting configuration JSON payloads.

    - Uses AES-256-GCM with a 96-bit nonce.
    - Derives a per-record subkey with HKDF-SHA256 using:
        info = b"config-json:v1" + (aad if provided)
      so that even if you reuse the master key, subkeys differ by AAD context.
    - AAD (associated data) is authenticated but not secret; store it if you’ll need it for decryption.
    """

    ALG = "AES-256-GCM"
    NONCE_SIZE = 12  # 96-bit, recommended for GCM

    def __init__(self, keyring: Keyring):
        self._keyring = keyring
        self._backend = default_backend()

    def _derive_subkey(self, master_key: bytes, aad: Optional[bytes]) -> bytes:
        info = b"config-json:v1" + (aad or b"")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,              # If you have an app-wide salt in a secure place, you can set it here.
            info=info,
            backend=self._backend
        )
        return hkdf.derive(master_key)

    def encrypt(self, plaintext_json: dict | str | bytes, aad: Optional[bytes] = None) -> CipherRecord:
        kid, master_key = self._keyring.active
        subkey = self._derive_subkey(master_key, aad)
        aesgcm = AESGCM(subkey)

        if isinstance(plaintext_json, dict):
            pt = json.dumps(plaintext_json, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        elif isinstance(plaintext_json, str):
            pt = plaintext_json.encode("utf-8")
        else:
            pt = plaintext_json  # bytes

        nonce = secrets.token_bytes(self.NONCE_SIZE)

        ct = aesgcm.encrypt(nonce, pt, aad)  # returns ciphertext||tag

        return CipherRecord(
            alg=self.ALG,
            kid=kid,
            n=b64e(nonce),
            ct=b64e(ct),
            aad=(b64e(aad) if aad else None),
        )

    def decrypt(self, record: CipherRecord, aad_override: Optional[bytes] = None) -> bytes:
        if not constant_time.bytes_eq(record.alg.encode(), self.ALG.encode()):
            raise ValueError(f"Unsupported alg: {record.alg}")

        key = self._keyring.get(record.kid)
        if key is None:
            raise ValueError(f"Unknown key id (kid) {record.kid}; key may have been retired without migration.")

        aad = aad_override if aad_override is not None else (b64d(record.aad) if record.aad else None)
        subkey = self._derive_subkey(key, aad)
        aesgcm = AESGCM(subkey)

        nonce = b64d(record.n)
        ct = b64d(record.ct)
        try:
            pt = aesgcm.decrypt(nonce, ct, aad)
        except InvalidTag as e:
            raise ValueError("Decryption failed: authentication tag mismatch (wrong key/AAD/nonce/ct).") from e

        return pt

    # Helpers for convenience when working with dicts
    def decrypt_to_json(self, record: CipherRecord, aad_override: Optional[bytes] = None) -> Any:
        pt = self.decrypt(record, aad_override=aad_override)
        return json.loads(pt.decode("utf-8"))
