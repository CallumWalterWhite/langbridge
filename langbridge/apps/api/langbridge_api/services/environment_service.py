from enum import Enum
import hashlib
import logging
import uuid
from typing import Any


from langbridge.packages.common.langbridge_common.config import settings
from langbridge.packages.common.langbridge_common.db.environment import OrganisationEnvironmentSetting
from langbridge.packages.common.langbridge_common.repositories.environment_repository import OrganizationEnvironmentSettingRepository
from langbridge.packages.common.langbridge_common.utils.encryptor import CipherRecord, ConfigCrypto, Keyring

class EnvironmentSettingKey(Enum):
    STAGING_DB_CONNECTION = "staging_db_connection"
    SUPPORT_EMAIL = "support_email"
    FEATURE_FLAG_NEW_DASHBOARD = "feature_flag_new_dashboard"
    DEFAULT_SEMANTIC_VECTOR_CONNECTOR = "default_semantic_vector_connector"


class EnvironmentService:
    def __init__(
        self,
        repository: OrganizationEnvironmentSettingRepository,
        crypto: ConfigCrypto | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logging.getLogger(__name__)
        self._crypto = crypto or self._build_crypto()

    def _build_crypto(self) -> ConfigCrypto:
        try:
            return ConfigCrypto(Keyring.from_env())
        except Exception as exc:  # noqa: BLE001 - we want to catch env misconfig
            # Fallback for local/dev when env is not configured
            self._logger.warning(
                "Falling back to derived local keyring for environment settings: %s",
                exc,
            )
            derived_key = hashlib.sha256(settings.SESSION_SECRET.encode("utf-8")).digest()
            return ConfigCrypto(Keyring({"local": derived_key}, "local"))

    def _aad(self, organization_id: uuid.UUID) -> bytes:
        return f"org:{organization_id}".encode("utf-8")

    def _encrypt_value(self, organization_id: uuid.UUID, value: Any) -> str:
        record = self._crypto.encrypt(value, aad=self._aad(organization_id))
        return record.to_json()

    def _decrypt_value(self, organization_id: uuid.UUID, ciphertext: str) -> str:
        record = CipherRecord.from_json(ciphertext)
        plaintext = self._crypto.decrypt(record, aad_override=self._aad(organization_id))
        return plaintext.decode("utf-8")

    async def set_setting(self, organization_id: uuid.UUID, key: str, value: Any) -> None:
        """Create or update an encrypted setting for the organization."""

        encrypted = self._encrypt_value(organization_id, value)
        existing = await self._repository.get_by_key(organization_id, key)
        if existing:
            existing.setting_value = encrypted
        else:
            setting = OrganisationEnvironmentSetting(
                id=uuid.uuid4(),
                organization_id=organization_id,
                setting_key=key,
                setting_value=encrypted,
            )
            self._repository.add(setting)
        await self._repository.flush()

    async def get_setting(self, organization_id: uuid.UUID, key: str, default: Any | None = None) -> Any | None:
        """Retrieve and decrypt a single setting. Returns default when missing."""

        existing = await self._repository.get_by_key(organization_id, key)
        if not existing:
            return default
        return self._decrypt_value(organization_id, existing.setting_value)

    #TODO: add decrypt flag to return encrypted values if needed
    async def list_settings(self, organization_id: uuid.UUID) -> dict[str, Any]:
        """Return all settings for an organization as a plain dict (decrypted)."""

        settings = await self._repository.list_for_organization(organization_id)
        return {
            setting.setting_key: self._decrypt_value(organization_id, setting.setting_value)
            for setting in settings
        }

    async def delete_setting(self, organization_id: uuid.UUID, key: str) -> None:
        """Delete a setting for the organization if it exists."""

        existing = await self._repository.get_by_key(organization_id, key)
        if not existing:
            return
        await self._repository.delete(existing)
        await self._repository.flush()

    def get_available_keys(self) -> list[str]:
        """Return a list of all available setting keys."""
        return list([key.value for key in EnvironmentSettingKey])
