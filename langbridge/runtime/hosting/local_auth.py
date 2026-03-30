
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import Field

from langbridge.runtime.hosting.passwords import hash_password, verify_password
from langbridge.runtime.persistence.uow import _ConfiguredRuntimePersistenceController
from langbridge.runtime.models.base import RuntimeModel


_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
_LOCAL_AUTH_PROVIDER = "runtime_local_session"
_RUNTIME_ADMIN_ROLE = "admin"
_RUNTIME_ALLOWED_ROLES = ("admin", "builder", "analyst", "viewer")
_RUNTIME_ROLE_ALIASES = {
    "runtime:admin": "admin",
    "runtime:builder": "builder",
    "runtime:analyst": "analyst",
    "runtime:viewer": "viewer",
}
_STATUS_ACTIVE = "active"
_STATUS_DISABLED = "disabled"


class RuntimeLocalAuthError(ValueError):
    pass


class RuntimeLocalAuthBootstrapRequiredError(RuntimeLocalAuthError):
    pass


class RuntimeLocalAuthAccount(RuntimeModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    subject: str
    username: str
    email: str
    display_name: str
    actor_type: str = "human"
    status: str = _STATUS_ACTIVE
    password_algorithm: str = "pbkdf2_sha256"
    password_updated_at: datetime
    must_rotate_password: bool = False
    password_hash: str
    roles: list[str] = Field(default_factory=lambda: [_RUNTIME_ADMIN_ROLE])
    created_at: datetime
    updated_at: datetime


class RuntimeManagedActor(RuntimeModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    subject: str
    username: str
    email: str
    display_name: str
    actor_type: str = "human"
    status: str = _STATUS_ACTIVE
    roles: list[str] = Field(default_factory=list)
    password_algorithm: str = "pbkdf2_sha256"
    password_updated_at: datetime
    must_rotate_password: bool = False
    created_at: datetime
    updated_at: datetime


class RuntimeLocalSession(RuntimeModel):
    id: uuid.UUID
    subject: str
    username: str
    email: str
    display_name: str
    roles: list[str] = Field(default_factory=list)
    provider: str = _LOCAL_AUTH_PROVIDER


class _RuntimeLocalAuthStore(Protocol):
    persistence_mode: Literal["in_memory", "sqlite", "postgres"]

    async def has_admin_account(self) -> bool:
        ...

    async def create_admin_account(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        password_algorithm: str,
    ) -> RuntimeLocalAuthAccount:
        ...

    async def get_account_by_identifier(
        self,
        *,
        identifier: str,
        include_disabled: bool = False,
    ) -> RuntimeLocalAuthAccount | None:
        ...

    async def get_account_by_id(
        self,
        *,
        actor_id: uuid.UUID,
        include_disabled: bool = False,
    ) -> RuntimeLocalAuthAccount | None:
        ...

    async def list_accounts(self) -> list[RuntimeLocalAuthAccount]:
        ...

    async def create_account(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        actor_type: str,
        roles: list[str],
        password_hash: str,
        password_algorithm: str,
    ) -> RuntimeLocalAuthAccount:
        ...

    async def update_account(
        self,
        *,
        actor_id: uuid.UUID,
        email: str | None = None,
        display_name: str | None = None,
        actor_type: str | None = None,
        status: str | None = None,
        roles: list[str] | None = None,
    ) -> RuntimeLocalAuthAccount:
        ...

    async def update_password(
        self,
        *,
        actor_id: uuid.UUID,
        password_hash: str,
        password_algorithm: str,
        must_rotate_password: bool,
    ) -> RuntimeLocalAuthAccount:
        ...

    async def get_session_secret(self) -> str | None:
        ...

    async def save_session_secret(self, *, secret: str) -> str:
        ...


class _InMemoryRuntimeLocalAuthStore:
    persistence_mode: Literal["in_memory"] = "in_memory"

    def __init__(self, *, workspace_id: uuid.UUID) -> None:
        self._workspace_id = workspace_id
        self._accounts: dict[uuid.UUID, RuntimeLocalAuthAccount] = {}
        self._session_secret: str | None = None

    async def has_admin_account(self) -> bool:
        return any(_is_active_admin(account) for account in self._accounts.values())

    async def create_admin_account(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        password_algorithm: str,
    ) -> RuntimeLocalAuthAccount:
        if await self.has_admin_account():
            raise RuntimeLocalAuthError("Runtime bootstrap has already been completed.")
        return await self.create_account(
            username=username,
            email=email,
            display_name=username,
            actor_type="human",
            roles=[_RUNTIME_ADMIN_ROLE],
            password_hash=password_hash,
            password_algorithm=password_algorithm,
        )

    async def get_account_by_identifier(
        self,
        *,
        identifier: str,
        include_disabled: bool = False,
    ) -> RuntimeLocalAuthAccount | None:
        normalized_identifier = _normalize_identifier(identifier)
        for account in self._accounts.values():
            if not include_disabled and account.status != _STATUS_ACTIVE:
                continue
            if (
                _normalize_identifier(account.username) == normalized_identifier
                or _normalize_identifier(account.email) == normalized_identifier
                or _normalize_identifier(account.subject) == normalized_identifier
            ):
                return account.model_copy(deep=True)
        return None

    async def get_account_by_id(
        self,
        *,
        actor_id: uuid.UUID,
        include_disabled: bool = False,
    ) -> RuntimeLocalAuthAccount | None:
        account = self._accounts.get(actor_id)
        if account is None:
            return None
        if not include_disabled and account.status != _STATUS_ACTIVE:
            return None
        return account.model_copy(deep=True)

    async def list_accounts(self) -> list[RuntimeLocalAuthAccount]:
        items = [account.model_copy(deep=True) for account in self._accounts.values()]
        items.sort(key=lambda account: account.created_at)
        return items

    async def create_account(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        actor_type: str,
        roles: list[str],
        password_hash: str,
        password_algorithm: str,
    ) -> RuntimeLocalAuthAccount:
        self._ensure_unique_actor(username=username, email=email)
        timestamp = datetime.now(timezone.utc)
        account = RuntimeLocalAuthAccount(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            subject=username,
            username=username,
            email=email,
            display_name=display_name,
            actor_type=actor_type,
            status=_STATUS_ACTIVE,
            password_algorithm=password_algorithm,
            password_updated_at=timestamp,
            must_rotate_password=False,
            password_hash=password_hash,
            roles=list(roles),
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._accounts[account.id] = account
        return account.model_copy(deep=True)

    async def update_account(
        self,
        *,
        actor_id: uuid.UUID,
        email: str | None = None,
        display_name: str | None = None,
        actor_type: str | None = None,
        status: str | None = None,
        roles: list[str] | None = None,
    ) -> RuntimeLocalAuthAccount:
        account = self._accounts.get(actor_id)
        if account is None:
            raise RuntimeLocalAuthError("Runtime actor was not found.")
        if email is not None and _normalize_identifier(email) != _normalize_identifier(account.email):
            self._ensure_unique_actor(username=None, email=email, exclude_actor_id=actor_id)
            account.email = email
        if display_name is not None:
            account.display_name = display_name
        if actor_type is not None:
            account.actor_type = actor_type
        if status is not None:
            account.status = status
        if roles is not None:
            account.roles = list(roles)
        account.updated_at = datetime.now(timezone.utc)
        return account.model_copy(deep=True)

    async def update_password(
        self,
        *,
        actor_id: uuid.UUID,
        password_hash: str,
        password_algorithm: str,
        must_rotate_password: bool,
    ) -> RuntimeLocalAuthAccount:
        account = self._accounts.get(actor_id)
        if account is None:
            raise RuntimeLocalAuthError("Runtime actor was not found.")
        timestamp = datetime.now(timezone.utc)
        account.password_hash = password_hash
        account.password_algorithm = password_algorithm
        account.password_updated_at = timestamp
        account.must_rotate_password = must_rotate_password
        account.updated_at = timestamp
        return account.model_copy(deep=True)

    async def get_session_secret(self) -> str | None:
        return self._session_secret

    async def save_session_secret(self, *, secret: str) -> str:
        self._session_secret = secret
        return secret

    def _ensure_unique_actor(
        self,
        *,
        username: str | None,
        email: str | None,
        exclude_actor_id: uuid.UUID | None = None,
    ) -> None:
        normalized_username = None if username is None else _normalize_identifier(username)
        normalized_email = None if email is None else _normalize_identifier(email)
        for account in self._accounts.values():
            if exclude_actor_id is not None and account.id == exclude_actor_id:
                continue
            if normalized_username and _normalize_identifier(account.username) == normalized_username:
                raise RuntimeLocalAuthError("A runtime actor already uses that username.")
            if normalized_email and _normalize_identifier(account.email) == normalized_email:
                raise RuntimeLocalAuthError("A runtime actor already uses that email.")


class _PersistedRuntimeLocalAuthStore:
    def __init__(
        self,
        *,
        workspace_id: uuid.UUID,
        persistence_mode: Literal["sqlite", "postgres"],
        controller: _ConfiguredRuntimePersistenceController,
    ) -> None:
        self.persistence_mode = persistence_mode
        self._workspace_id = workspace_id
        self._controller = controller

    async def has_admin_account(self) -> bool:
        return any(_is_active_admin(account) for account in await self.list_accounts())

    async def create_admin_account(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        password_algorithm: str,
    ) -> RuntimeLocalAuthAccount:
        if await self.has_admin_account():
            raise RuntimeLocalAuthError("Runtime bootstrap has already been completed.")
        return await self.create_account(
            username=username,
            email=email,
            display_name=username,
            actor_type="human",
            roles=[_RUNTIME_ADMIN_ROLE],
            password_hash=password_hash,
            password_algorithm=password_algorithm,
        )

    async def get_account_by_identifier(
        self,
        *,
        identifier: str,
        include_disabled: bool = False,
    ) -> RuntimeLocalAuthAccount | None:
        async with self._controller.unit_of_work() as uow:
            repository = uow.repository("local_auth_repository")
            credential = await repository.get_by_identifier(
                workspace_id=self._workspace_id,
                identifier=identifier,
            )
            if credential is None:
                return None
            account = _credential_to_account(credential)
            if not include_disabled and account.status != _STATUS_ACTIVE:
                return None
            return account

    async def get_account_by_id(
        self,
        *,
        actor_id: uuid.UUID,
        include_disabled: bool = False,
    ) -> RuntimeLocalAuthAccount | None:
        async with self._controller.unit_of_work() as uow:
            repository = uow.repository("local_auth_repository")
            credential = await repository.get_by_actor_id(actor_id=actor_id)
            if credential is None or credential.workspace_id != self._workspace_id:
                return None
            account = _credential_to_account(credential)
            if not include_disabled and account.status != _STATUS_ACTIVE:
                return None
            return account

    async def list_accounts(self) -> list[RuntimeLocalAuthAccount]:
        async with self._controller.unit_of_work() as uow:
            repository = uow.repository("local_auth_repository")
            credentials = await repository.list_for_workspace(workspace_id=self._workspace_id)
            return [_credential_to_account(credential) for credential in credentials]

    async def create_account(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        actor_type: str,
        roles: list[str],
        password_hash: str,
        password_algorithm: str,
    ) -> RuntimeLocalAuthAccount:
        from langbridge.runtime.persistence.db.auth import RuntimeLocalAuthCredential
        from langbridge.runtime.persistence.db.workspace import RuntimeActor

        async with self._controller.unit_of_work() as uow:
            workspace_repository = uow.repository("workspace_repository")
            actor_repository = uow.repository("actor_repository")
            auth_repository = uow.repository("local_auth_repository")

            await workspace_repository.ensure_configured(
                workspace_id=self._workspace_id,
                name=f"local-runtime-{self._workspace_id}",
            )
            await self._ensure_unique_actor(
                actor_repository=actor_repository,
                username=username,
                email=email,
            )
            timestamp = datetime.now(timezone.utc)
            actor = RuntimeActor(
                id=uuid.uuid4(),
                workspace_id=self._workspace_id,
                subject=username,
                username=username,
                actor_type=actor_type,
                status=_STATUS_ACTIVE,
                email=email,
                display_name=display_name,
                roles_json=list(roles),
                is_active=True,
                metadata_json={
                    "provider": _LOCAL_AUTH_PROVIDER,
                    "runtime_operator": True,
                    "local_auth": True,
                },
            )
            credential = RuntimeLocalAuthCredential(
                actor_id=actor.id,
                workspace_id=self._workspace_id,
                password_hash=password_hash,
                password_algorithm=password_algorithm,
                password_updated_at=timestamp,
                must_rotate_password=False,
            )
            credential.actor = actor
            actor_repository.add(actor)
            auth_repository.add(credential)
            await uow.flush()
            account = _credential_to_account(credential)
            await uow.commit()
            return account

    async def update_account(
        self,
        *,
        actor_id: uuid.UUID,
        email: str | None = None,
        display_name: str | None = None,
        actor_type: str | None = None,
        status: str | None = None,
        roles: list[str] | None = None,
    ) -> RuntimeLocalAuthAccount:
        async with self._controller.unit_of_work() as uow:
            actor_repository = uow.repository("actor_repository")
            auth_repository = uow.repository("local_auth_repository")
            credential = await auth_repository.get_by_actor_id(actor_id=actor_id)
            if credential is None or credential.workspace_id != self._workspace_id:
                raise RuntimeLocalAuthError("Runtime actor was not found.")
            actor = credential.actor
            if actor is None:
                raise RuntimeLocalAuthError("Runtime local auth credential is missing its actor.")
            if email is not None and _normalize_identifier(email) != _normalize_identifier(actor.email):
                await self._ensure_unique_actor(
                    actor_repository=actor_repository,
                    username=None,
                    email=email,
                    exclude_actor_id=actor.id,
                )
                actor.email = email
            if display_name is not None:
                actor.display_name = display_name
            if actor_type is not None:
                actor.actor_type = actor_type
            if status is not None:
                actor.status = status
                actor.is_active = status == _STATUS_ACTIVE
            if roles is not None:
                actor.roles_json = list(roles)
            actor.metadata_json = {
                **dict(actor.metadata_json or {}),
                "provider": _LOCAL_AUTH_PROVIDER,
                "runtime_operator": True,
                "local_auth": True,
            }
            await uow.flush()
            account = _credential_to_account(credential)
            await uow.commit()
            return account

    async def update_password(
        self,
        *,
        actor_id: uuid.UUID,
        password_hash: str,
        password_algorithm: str,
        must_rotate_password: bool,
    ) -> RuntimeLocalAuthAccount:
        async with self._controller.unit_of_work() as uow:
            repository = uow.repository("local_auth_repository")
            credential = await repository.get_by_actor_id(actor_id=actor_id)
            if credential is None or credential.workspace_id != self._workspace_id:
                raise RuntimeLocalAuthError("Runtime actor was not found.")
            timestamp = datetime.now(timezone.utc)
            credential.password_hash = password_hash
            credential.password_algorithm = password_algorithm
            credential.password_updated_at = timestamp
            credential.must_rotate_password = must_rotate_password
            await uow.flush()
            account = _credential_to_account(credential)
            await uow.commit()
            return account

    async def get_session_secret(self) -> str | None:
        async with self._controller.unit_of_work() as uow:
            repository = uow.repository("local_auth_state_repository")
            state = await repository.get_for_workspace(workspace_id=self._workspace_id)
            if state is None:
                return None
            return str(state.session_secret or "").strip() or None

    async def save_session_secret(self, *, secret: str) -> str:
        from langbridge.runtime.persistence.db.auth import RuntimeLocalAuthState

        async with self._controller.unit_of_work() as uow:
            workspace_repository = uow.repository("workspace_repository")
            state_repository = uow.repository("local_auth_state_repository")

            await workspace_repository.ensure_configured(
                workspace_id=self._workspace_id,
                name=f"local-runtime-{self._workspace_id}",
            )
            state = await state_repository.get_for_workspace(workspace_id=self._workspace_id)
            if state is None:
                state = RuntimeLocalAuthState(
                    workspace_id=self._workspace_id,
                    session_secret=secret,
                )
                state_repository.add(state)
            else:
                state.session_secret = secret
            await uow.flush()
            await uow.commit()
            return state.session_secret

    async def _ensure_unique_actor(
        self,
        *,
        actor_repository: Any,
        username: str | None,
        email: str | None,
        exclude_actor_id: uuid.UUID | None = None,
    ) -> None:
        if username is not None:
            existing_actor = await actor_repository.get_by_username(
                workspace_id=self._workspace_id,
                username=username,
            )
            if existing_actor is not None and existing_actor.id != exclude_actor_id:
                raise RuntimeLocalAuthError("A runtime actor already uses that username.")
        if email is not None:
            existing_email_actor = await actor_repository.get_by_email(
                workspace_id=self._workspace_id,
                email=email,
            )
            if existing_email_actor is not None and existing_email_actor.id != exclude_actor_id:
                raise RuntimeLocalAuthError("A runtime actor already uses that email.")


class RuntimeLocalAuthManager:
    def __init__(
        self,
        *,
        workspace_id: uuid.UUID,
        persistence_mode: Literal["in_memory", "sqlite", "postgres"],
        cookie_name: str,
        session_max_age_seconds: int,
        session_secret: str | None = None,
        persistence_controller: _ConfiguredRuntimePersistenceController | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        self._cookie_name = str(cookie_name or "").strip() or "langbridge_runtime_session"
        self._session_max_age_seconds = max(60, int(session_max_age_seconds))
        self._session_secret = str(session_secret or "").strip() or None
        if persistence_mode == "in_memory":
            self._store: _RuntimeLocalAuthStore = _InMemoryRuntimeLocalAuthStore(workspace_id=workspace_id)
        else:
            if persistence_controller is None:
                raise ValueError("Persisted local auth requires a runtime persistence controller.")
            self._store = _PersistedRuntimeLocalAuthStore(
                workspace_id=workspace_id,
                persistence_mode=persistence_mode,
                controller=persistence_controller,
            )

    @property
    def cookie_name(self) -> str:
        return self._cookie_name

    @property
    def session_max_age_seconds(self) -> int:
        return self._session_max_age_seconds

    @property
    def persistence_mode(self) -> Literal["in_memory", "sqlite", "postgres"]:
        return self._store.persistence_mode

    async def auth_status(self) -> dict[str, bool]:
        has_admin = await self._store.has_admin_account()
        return {
            "has_admin": has_admin,
            "bootstrap_required": not has_admin,
        }

    async def list_actors(self) -> list[RuntimeManagedActor]:
        return [_to_managed_actor(account) for account in await self._store.list_accounts()]

    async def bootstrap_admin(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> RuntimeLocalSession:
        normalized_username = _normalize_username(username)
        normalized_email = _normalize_email(email)
        _validate_password(password)

        account = await self._store.create_admin_account(
            username=normalized_username,
            email=normalized_email,
            password_hash=hash_password(password),
            password_algorithm="pbkdf2_sha256",
        )
        return self._to_session(account)

    async def create_actor(
        self,
        *,
        username: str,
        email: str,
        password: str,
        display_name: str | None = None,
        actor_type: str | None = None,
        roles: list[str] | tuple[str, ...] | None = None,
    ) -> RuntimeManagedActor:
        normalized_username = _normalize_username(username)
        normalized_email = _normalize_email(email)
        normalized_display_name = _normalize_display_name(display_name, normalized_username)
        normalized_actor_type = _normalize_actor_type(actor_type)
        normalized_roles = _normalize_runtime_roles(roles)
        _validate_password(password)
        account = await self._store.create_account(
            username=normalized_username,
            email=normalized_email,
            display_name=normalized_display_name,
            actor_type=normalized_actor_type,
            roles=normalized_roles,
            password_hash=hash_password(password),
            password_algorithm="pbkdf2_sha256",
        )
        return _to_managed_actor(account)

    async def update_actor(
        self,
        *,
        actor_id: uuid.UUID,
        email: str | None = None,
        display_name: str | None = None,
        actor_type: str | None = None,
        status: str | None = None,
        roles: list[str] | tuple[str, ...] | None = None,
    ) -> RuntimeManagedActor:
        existing = await self._require_account(actor_id=actor_id, include_disabled=True)
        normalized_email = None if email is None else _normalize_email(email)
        normalized_display_name = None if display_name is None else _normalize_display_name(display_name, existing.username)
        normalized_actor_type = None if actor_type is None else _normalize_actor_type(actor_type)
        normalized_status = None if status is None else _normalize_actor_status(status)
        normalized_roles = None if roles is None else _normalize_runtime_roles(roles)
        await self._ensure_active_admin_remains(
            actor_id=actor_id,
            next_status=normalized_status or existing.status,
            next_roles=normalized_roles or list(existing.roles),
        )
        account = await self._store.update_account(
            actor_id=actor_id,
            email=normalized_email,
            display_name=normalized_display_name,
            actor_type=normalized_actor_type,
            status=normalized_status,
            roles=normalized_roles,
        )
        return _to_managed_actor(account)

    async def reset_password(
        self,
        *,
        actor_id: uuid.UUID,
        password: str,
        must_rotate_password: bool = False,
    ) -> RuntimeManagedActor:
        await self._require_account(actor_id=actor_id, include_disabled=True)
        _validate_password(password)
        account = await self._store.update_password(
            actor_id=actor_id,
            password_hash=hash_password(password),
            password_algorithm="pbkdf2_sha256",
            must_rotate_password=bool(must_rotate_password),
        )
        return _to_managed_actor(account)

    async def authenticate(
        self,
        *,
        identifier: str,
        password: str,
    ) -> RuntimeLocalSession:
        normalized_identifier = _normalize_identifier(identifier)
        if not normalized_identifier:
            raise RuntimeLocalAuthError("Username or email is required.")

        if not await self._store.has_admin_account():
            raise RuntimeLocalAuthBootstrapRequiredError("Runtime bootstrap setup is required.")

        account = await self._store.get_account_by_identifier(
            identifier=normalized_identifier,
            include_disabled=True,
        )
        if account is None or not verify_password(password, account.password_hash):
            raise RuntimeLocalAuthError("Invalid username, email, or password.")
        if account.status != _STATUS_ACTIVE:
            raise RuntimeLocalAuthError("This runtime user is disabled.")

        return self._to_session(account)

    async def issue_session_token(self, session: RuntimeLocalSession) -> str:
        serializer = URLSafeTimedSerializer(
            secret_key=await self._resolve_session_secret(),
            salt="langbridge-runtime-session",
        )
        return serializer.dumps(
            {
                "workspace_id": str(self._workspace_id),
                "actor_id": str(session.id),
                "provider": session.provider,
                "version": 2,
            }
        )

    async def authenticate_session_request(self, request: Request) -> RuntimeLocalSession:
        if not await self._store.has_admin_account():
            raise RuntimeLocalAuthBootstrapRequiredError("Runtime bootstrap setup is required.")

        token = self._extract_cookie_token(request)
        serializer = URLSafeTimedSerializer(
            secret_key=await self._resolve_session_secret(),
            salt="langbridge-runtime-session",
        )
        try:
            payload = serializer.loads(token, max_age=self._session_max_age_seconds)
        except SignatureExpired as exc:
            raise RuntimeLocalAuthError("Runtime session has expired.") from exc
        except BadSignature as exc:
            raise RuntimeLocalAuthError("Runtime session is invalid.") from exc

        workspace_id_raw = str(payload.get("workspace_id") or "").strip()
        if workspace_id_raw != str(self._workspace_id):
            raise RuntimeLocalAuthError("Runtime session is invalid.")

        actor_id_raw = str(payload.get("actor_id") or "").strip()
        if not actor_id_raw:
            raise RuntimeLocalAuthError("Runtime session is invalid.")
        try:
            actor_id = uuid.UUID(actor_id_raw)
        except ValueError as exc:
            raise RuntimeLocalAuthError("Runtime session is invalid.") from exc

        account = await self._store.get_account_by_id(actor_id=actor_id)
        if account is None:
            raise RuntimeLocalAuthError("Runtime session is no longer valid.")
        return self._to_session(account)

    async def authenticate_request(self, request: Request) -> RuntimeLocalSession:
        return await self.authenticate_session_request(request)

    def delete_session_cookie(self, response: Any) -> None:
        response.delete_cookie(self._cookie_name, path="/")

    async def _require_account(
        self,
        *,
        actor_id: uuid.UUID,
        include_disabled: bool,
    ) -> RuntimeLocalAuthAccount:
        account = await self._store.get_account_by_id(
            actor_id=actor_id,
            include_disabled=include_disabled,
        )
        if account is None:
            raise RuntimeLocalAuthError("Runtime actor was not found.")
        return account

    async def _ensure_active_admin_remains(
        self,
        *,
        actor_id: uuid.UUID,
        next_status: str,
        next_roles: list[str],
    ) -> None:
        active_admins = 0
        for account in await self._store.list_accounts():
            status = account.status
            roles = list(account.roles)
            if account.id == actor_id:
                status = next_status
                roles = list(next_roles)
            if status == _STATUS_ACTIVE and _has_admin_role(roles):
                active_admins += 1
        if active_admins == 0:
            raise RuntimeLocalAuthError("At least one active admin runtime user is required.")

    def _extract_cookie_token(self, request: Request) -> str:
        token = str(request.cookies.get(self._cookie_name) or "").strip()
        if token:
            return token
        raise RuntimeLocalAuthError("Runtime session is required.")

    async def _resolve_session_secret(self) -> str:
        if self._session_secret:
            persisted_secret = await self._store.get_session_secret()
            if persisted_secret != self._session_secret:
                await self._store.save_session_secret(secret=self._session_secret)
            return self._session_secret

        persisted_secret = await self._store.get_session_secret()
        if persisted_secret:
            return persisted_secret

        generated_secret = secrets.token_urlsafe(32)
        await self._store.save_session_secret(secret=generated_secret)
        return generated_secret

    @staticmethod
    def _to_session(account: RuntimeLocalAuthAccount) -> RuntimeLocalSession:
        return RuntimeLocalSession(
            id=account.id,
            subject=account.subject,
            username=account.username,
            email=account.email,
            display_name=account.display_name,
            roles=list(account.roles),
        )


def _to_managed_actor(account: RuntimeLocalAuthAccount) -> RuntimeManagedActor:
    return RuntimeManagedActor.model_validate(account.model_dump(exclude={"password_hash"}))


def _credential_to_account(credential: Any) -> RuntimeLocalAuthAccount:
    actor = credential.actor
    if actor is None:
        raise RuntimeLocalAuthError("Runtime local auth credential is missing its actor.")
    credential_created_at = getattr(credential, "__dict__", {}).get("created_at")
    credential_updated_at = getattr(credential, "__dict__", {}).get("updated_at")
    actor_created_at = getattr(actor, "__dict__", {}).get("created_at")
    actor_updated_at = getattr(actor, "__dict__", {}).get("updated_at")
    return RuntimeLocalAuthAccount(
        id=actor.id,
        workspace_id=actor.workspace_id,
        subject=str(actor.subject or getattr(actor, "username", None) or ""),
        username=_coerce_actor_username(actor),
        email=str(actor.email or ""),
        display_name=str(actor.display_name or getattr(actor, "username", None) or actor.subject or ""),
        actor_type=str(actor.actor_type or "human"),
        status=_coerce_actor_status(actor),
        password_algorithm=str(getattr(credential, "password_algorithm", None) or "pbkdf2_sha256"),
        password_updated_at=(
            getattr(credential, "password_updated_at", None)
            or credential_updated_at
            or credential_created_at
            or actor_updated_at
            or actor_created_at
            or datetime.now(timezone.utc)
        ),
        must_rotate_password=bool(getattr(credential, "must_rotate_password", False)),
        password_hash=credential.password_hash,
        roles=_normalize_stored_roles(list(actor.roles_json or [])),
        created_at=credential_created_at or actor_created_at or datetime.now(timezone.utc),
        updated_at=credential_updated_at or actor_updated_at or datetime.now(timezone.utc),
    )


def _normalize_username(value: str) -> str:
    normalized = str(value or "").strip()
    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise RuntimeLocalAuthError(
            "Username must be 3-64 characters and use letters, numbers, dots, underscores, or hyphens."
        )
    return normalized


def _normalize_email(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise RuntimeLocalAuthError("A valid email address is required.")
    return normalized


def _normalize_identifier(value: str) -> str:
    return str(value or "").strip().casefold()


def _normalize_display_name(value: str | None, fallback_username: str) -> str:
    normalized = str(value or "").strip()
    return normalized or fallback_username


def _normalize_actor_type(value: str | None) -> str:
    normalized = str(value or "human").strip().lower()
    return normalized or "human"


def _normalize_actor_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"enabled", _STATUS_ACTIVE}:
        return _STATUS_ACTIVE
    if normalized in {"disabled", _STATUS_DISABLED}:
        return _STATUS_DISABLED
    raise RuntimeLocalAuthError("Runtime actor status must be 'active' or 'disabled'.")


def _normalize_runtime_roles(value: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized_roles: list[str] = []
    seen: set[str] = set()
    for raw_role in value or ():
        role = _RUNTIME_ROLE_ALIASES.get(str(raw_role or "").strip().lower(), str(raw_role or "").strip().lower())
        if not role:
            continue
        if role not in _RUNTIME_ALLOWED_ROLES:
            raise RuntimeLocalAuthError("Runtime roles must be drawn from: admin, builder, analyst, viewer.")
        if role not in seen:
            seen.add(role)
            normalized_roles.append(role)
    if not normalized_roles:
        raise RuntimeLocalAuthError("At least one runtime role is required.")
    return normalized_roles


def _normalize_stored_roles(value: list[str] | tuple[str, ...]) -> list[str]:
    normalized_roles: list[str] = []
    seen: set[str] = set()
    for raw_role in value:
        role = _RUNTIME_ROLE_ALIASES.get(str(raw_role or "").strip().lower(), str(raw_role or "").strip().lower())
        if role not in _RUNTIME_ALLOWED_ROLES or role in seen:
            continue
        seen.add(role)
        normalized_roles.append(role)
    return normalized_roles or ["viewer"]


def _coerce_actor_username(actor: Any) -> str:
    username = str(getattr(actor, "username", None) or "").strip()
    if username:
        return username
    subject = str(getattr(actor, "subject", None) or "").strip()
    if subject:
        return subject
    raise RuntimeLocalAuthError("Runtime actor is missing its username.")


def _coerce_actor_status(actor: Any) -> str:
    status = str(getattr(actor, "status", None) or "").strip().lower()
    if status in {_STATUS_ACTIVE, _STATUS_DISABLED}:
        return status
    return _STATUS_ACTIVE if bool(getattr(actor, "is_active", True)) else _STATUS_DISABLED


def _has_admin_role(roles: list[str] | tuple[str, ...]) -> bool:
    return "admin" in _normalize_stored_roles(list(roles))


def _is_active_admin(account: RuntimeLocalAuthAccount) -> bool:
    return account.status == _STATUS_ACTIVE and _has_admin_role(account.roles)


def _validate_password(value: str) -> None:
    if len(str(value or "")) < 8:
        raise RuntimeLocalAuthError("Password must be at least 8 characters.")
