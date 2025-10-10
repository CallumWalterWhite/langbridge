from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic
from dependency_injector.wiring import Provide, inject

from ioc import Container
from db.auth import OAuthAccount, User
from auth.jwt import create_jwt, set_session_cookie, verify_jwt
from services.auth_service import AuthService
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBasic()

SUPPORTED_PROVIDERS = {"github", "google"}


def _normalize_provider(provider: str) -> str:
    normalized = provider.lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unsupported auth provider '{provider}'",
        )
    return normalized


async def _authorize_with_provider(
    provider: str,
    request: Request,
    auth_service: AuthService,
):
    normalized = _normalize_provider(provider)
    redirect_uri = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/{normalized}/callback"
    return await auth_service.authorize_redirect(request, normalized, redirect_uri)  # type: ignore[arg-type]


async def _handle_oauth_callback(
    provider: str,
    request: Request,
    auth_service: AuthService,
):
    normalized = _normalize_provider(provider)
    user: User = await auth_service.authenticate_callback(request, normalized)  # type: ignore[arg-type]

    oauth_account: Optional[OAuthAccount] = next(
        (oa for oa in user.oauth_accounts if oa.provider == normalized),
        None,
    )

    if not oauth_account:
        raise HTTPException(status_code=400, detail="OAuth account not found for user")

    session_claims = {
        "sub": oauth_account.sub,
        "username": user.username,
        "name": oauth_account.name,
        "avatar_url": oauth_account.avatar_url,
        "email": oauth_account.email,
        "provider": normalized,
    }

    jwt_token = create_jwt(session_claims)

    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard", status_code=303)
    set_session_cookie(redirect, jwt_token)
    return redirect

@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/login/github")
@inject
async def login_github(
        request: Request,
        auth_service: AuthService = Depends(Provide[Container.auth_service])):
    return await _authorize_with_provider("github", request, auth_service)

@router.get("/login/google")
@inject
async def login_google(
        request: Request,
        auth_service: AuthService = Depends(Provide[Container.auth_service])):
    return await _authorize_with_provider("google", request, auth_service)

@router.get("/login/{provider}")
@inject
async def login_provider(
    provider: str,
    request: Request,
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    return await _authorize_with_provider(provider, request, auth_service)

@router.get("/github/callback")
@inject
async def auth_github_callback(
    request: Request,
    auth_service: AuthService = Depends(Provide[Container.auth_service])):
    return await _handle_oauth_callback("github", request, auth_service)

@router.get("/google/callback")
@inject
async def auth_google_callback(
    request: Request,
    auth_service: AuthService = Depends(Provide[Container.auth_service])):
    return await _handle_oauth_callback("google", request, auth_service)

@router.get("/{provider}/callback")
@inject
async def auth_provider_callback(
    provider: str,
    request: Request,
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    return await _handle_oauth_callback(provider, request, auth_service)

@router.get("/logout")
@inject
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(settings.COOKIE_NAME, path="/")
    return resp


@router.get("/me")
@inject
async def me(request: Request):
    token: Optional[str] = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthenticated")
    claims = verify_jwt(token)
    return {"user": claims}
