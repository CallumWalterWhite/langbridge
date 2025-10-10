from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
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

@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/login/github")
@inject
async def login_github(
        request: Request,
        auth_service: AuthService = Depends(Provide[Container.auth_service])):
    redirect_uri = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/github/callback"
    return await auth_service.authorize_redirect(request, 'github', redirect_uri)

@router.get("/github/callback")
@inject
async def auth_github_callback(
    request: Request,
    auth_service: AuthService = Depends(Provide[Container.auth_service])):
    user: User = await auth_service.authenticate_callback(request, 'github')
    
    oauth_account: Optional[OAuthAccount] = next(
        (oa for oa in user.oauth_accounts if oa.provider == 'github'),
        None
    )
    
    if not oauth_account:
        raise HTTPException(status_code=400, detail="OAuth account not found for user")

    session_claims = {
        "sub": oauth_account.sub,
        "username": user.username,
        "name": oauth_account.name,
        "avatar_url": oauth_account.avatar_url,
        "email": oauth_account.email,
        "provider": "github",
    }

    jwt_token = create_jwt(session_claims)

    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard", status_code=303)  # 303 avoids odd downloads
    set_session_cookie(redirect, jwt_token)
    return redirect

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
