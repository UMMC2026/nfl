from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    # Underdog Pick'em: 2–8 legs; enforce 2+ teams
    max_legs: int = 8
    min_teams_per_entry: int = 2

    db_url: str = os.getenv("DB_URL", "sqlite:///./ufa.db")
    cfbd_api_key: str | None = os.getenv("CFBD_API_KEY")

settings = Settings()
