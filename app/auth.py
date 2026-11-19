"""The ONE place that decides who the user is.

Today: Cloudflare Access puts the logged-in email in a header.
Later: swap this function for your own login (Phase 4) and nothing else changes.
"""

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from app import services
from app.config import settings
from app.db import get_session
from app.models import User


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    email = request.headers.get("cf-access-authenticated-user-email")
    if not email:
        if not settings.dev_mode:
            raise HTTPException(status_code=401, detail="Not logged in")  # fail closed
        email = settings.dev_email
    email = email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = services.create_user(session, email)
    return user
