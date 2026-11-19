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


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
