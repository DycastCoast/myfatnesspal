"""Settings come from environment variables, so the same image runs anywhere."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo


class Settings:
    def __init__(self):
        self.data_dir = Path(os.environ.get("DATA_DIR", "./data"))
        self.db_path = self.data_dir / "myfatnesspal.db"
        # DEV_MODE=1 lets you use the app without Cloudflare (laptop only!).
        self.dev_mode = os.environ.get("DEV_MODE") == "1"
        self.dev_email = os.environ.get("DEV_EMAIL", "dev@localhost")
        self.tz = ZoneInfo(os.environ.get("APP_TZ", "Europe/London"))
        self.off_timeout = float(os.environ.get("OFF_TIMEOUT", "6"))
        self.contact = os.environ.get("CONTACT", "github.com/DycastCoast/myfatnesspal")
        self.default_goal_kcal = int(os.environ.get("DEFAULT_GOAL_KCAL", "2000"))
        # Who may download a full backup. Empty = the first user ever created (you).
        self.admin_emails = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

        # Login: "cloudflare" (montlab) or "tailscale" (Raspberry Pi). See app/auth.py.
        self.auth_mode = os.environ.get("AUTH_MODE", "cloudflare").strip().lower()
        if self.auth_mode not in ("cloudflare", "tailscale"):
            raise ValueError(f"AUTH_MODE must be cloudflare or tailscale, not {self.auth_mode!r}")
        # Only these logins get in (comma-separated). Empty = anyone the login layer lets through.
        self.allowed_logins = {e.strip().lower() for e in os.environ.get("ALLOWED_LOGINS", "").split(",") if e.strip()}
        # Single-person mode: every allowed login uses this account's diary.
        self.account_email = os.environ.get("ACCOUNT_EMAIL", "").strip().lower()


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
