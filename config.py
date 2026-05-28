import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")


class Settings:
    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    ALERT_RECIPIENT: str = os.getenv("ALERT_RECIPIENT", GMAIL_USER)
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    SCRAPE_INTERVAL_HOURS: int = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )

    @classmethod
    def validate(cls) -> list[str]:
        errors: list[str] = []
        if not cls.GMAIL_USER or "@" not in cls.GMAIL_USER:
            errors.append("GMAIL_USER must be a valid email address")
        if not cls.GMAIL_APP_PASSWORD:
            errors.append("GMAIL_APP_PASSWORD is required")
        if cls.SCRAPE_INTERVAL_HOURS < 1:
            errors.append("SCRAPE_INTERVAL_HOURS must be >= 1")
        return errors
