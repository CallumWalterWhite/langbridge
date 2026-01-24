from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from jose import jwt, JWTError

from langbridge.packages.common.langbridge_common.config import settings

def create_jwt(payload: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRES_MIN)
    to_encode = payload | {"exp": exp}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError as e:
        raise JWTError("Invalid or expired token") from e
    
def set_session_cookie(resp: RedirectResponse | JSONResponse, token: str) -> None:
    resp.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE, # set True in production with HTTPS
        samesite="lax",
        max_age=settings.JWT_EXPIRES_MIN * 60,
        path="/",
    )