from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    BASE_MUSIC_PATH: Path
    LOG_FILE: Path
    COOKIES_FILE: Path
    LASTFM_API_KEY: str = ""
    LASTFM_API_SECRET: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
