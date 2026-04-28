"""Google OAuth login + email-domain allowlist gate.

Set DEV_AUTH_BYPASS=true to skip the OAuth flow during local development.
In production set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URL,
SESSION_SECRET and ALLOWED_EMAIL_DOMAINS.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings


def install_session_middleware(app) -> None:
    settings = get_settings()
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="vmt_session",
        same_site="lax",
        https_only=False,
    )


def _email_allowed(email: str) -> bool:
    settings = get_settings()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1].lower()
    return domain in settings.allowed_domains_list


async def require_user(request: Request) -> dict:
    settings = get_settings()
    if settings.dev_auth_bypass:
        return {"email": "dev@devoteam.com", "name": "Local Dev", "picture": ""}
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    if not _email_allowed(user.get("email", "")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email domain not allowed")
    return user


def get_oauth_client():
    """Lazy import so missing OAuth env doesn't break tests."""
    from authlib.integrations.starlette_client import OAuth

    settings = get_settings()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


async def login_redirect(request: Request) -> RedirectResponse:
    settings = get_settings()
    if settings.dev_auth_bypass:
        return RedirectResponse("/")
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="OAuth not configured")
    oauth = get_oauth_client()
    redirect_uri = settings.oauth_redirect_url or str(request.url_for("auth_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


async def oauth_callback(request: Request) -> RedirectResponse:
    settings = get_settings()
    if settings.dev_auth_bypass:
        return RedirectResponse("/")
    oauth = get_oauth_client()
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.parse_id_token(request, token)
    email = (userinfo or {}).get("email", "")
    if not _email_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Email domain not in allowlist: {email}",
        )
    request.session["user"] = {
        "email": email,
        "name": userinfo.get("name", ""),
        "picture": userinfo.get("picture", ""),
    }
    return RedirectResponse("/")


def logout(request: Request) -> RedirectResponse:
    request.session.pop("user", None)
    return RedirectResponse("/")
