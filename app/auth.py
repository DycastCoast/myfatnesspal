"""The ONE place that decides who the user is.

Two ways in, chosen by AUTH_MODE:

- "cloudflare" (default, for montlab): Cloudflare Access puts the logged-in email in a header.
- "tailscale" (for the Raspberry Pi): `tailscale serve` puts your Tailscale login in a header.
  Only safe because the app listens on 127.0.0.1, so `tailscale serve` is the only way to reach it.

Either way it fails closed: no trusted header, no entry.
"""

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from app import services
from app.config import settings
from app.db import get_session
from app.models import User

HEADERS = {
    "cloudflare": "cf-access-authenticated-user-email",
    "tailscale": "tailscale-user-login",
}


def who_is_asking(request: Request) -> str:
    """The account email for this request, or a 401/403."""
    login = (request.headers.get(HEADERS[settings.auth_mode]) or "").strip().lower()
    if not login:
        if not settings.dev_mode:
            raise HTTPException(status_code=401, detail="Not logged in")
        login = settings.dev_email
    if settings.allowed_logins and login not in settings.allowed_logins and not settings.dev_mode:
        raise HTTPException(status_code=403, detail="This account isn't allowed in")
    # Single-person setup: whoever is let in uses the one diary, whatever their login looks like.
    return settings.account_email or login


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    email = who_is_asking(request)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = services.create_user(session, email)
    return user
