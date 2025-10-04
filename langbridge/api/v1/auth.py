from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dependency_injector.wiring import Provide, inject
import httpx

from ioc import Container
from langbridge.langbridge.db.auth import User
from auth.jwt import create_jwt, set_session_cookie, verify_jwt
from schemas.auth import LoginResponse, RegisterRequest, UserResponse
from services.auth_service import AuthService
from config import settings
from authlib.integrations.starlette_client import OAuth, OAuthError

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBasic()

@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/login/github")
@inject
async def login_github(
        request: Request,
        oauth: OAuth = Depends(Provide[Container.oauth])):
    redirect_uri = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri) # type: ignore

@router.get("/github/callback")
@inject
async def auth_github_callback(
    request: Request,
    oauth: OAuth = Depends(Provide[Container.oauth])):
    try:
        token = await oauth.github.authorize_access_token(request) # type: ignore
    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e.error}")

    # Never return the token to the browser -- exchange happens server-side only
    async with httpx.AsyncClient() as client:
        user_resp = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token['access_token']}"})
        user_resp.raise_for_status()
        user = user_resp.json()

        email_resp = await client.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {token['access_token']}"})
        email_resp.raise_for_status()
        emails = email_resp.json()

    primary_email = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)

    session_claims = {
        "sub": str(user.get("id")),
        "username": user.get("login"),
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
        "email": primary_email,
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
