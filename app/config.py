from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
<<<<<<< HEAD
    BASE_MUSIC_PATH: Path = Path("/mnt/data_pool/music")
    LOG_FILE: Path = Path("/app/logs/downloader.log")
    HISTORY_FILE: Path = Path("/app/logs/history.jsonl")
    STATE_DIR: Path = Path("/app/logs/jobstate")
    COOKIES_FILE: Path = Path("/app/cookies.txt")
=======

    BASE_MUSIC_PATH: Path
    LOG_FILE: Path
    COOKIES_FILE: Path
>>>>>>> ed76a6993d95e6e0ce87e137bae0a38c8ff30b7d
    LASTFM_API_KEY: str = ""
    LASTFM_API_SECRET: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
