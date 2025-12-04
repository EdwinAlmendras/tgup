"""Configuration - single source of truth."""
import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class MediaType(Enum):
    VIDEO = "video"
    PHOTO = "photo"
    DOCUMENT = "document"


class MediaFilter(Enum):
    ALL = "all"
    VIDEO = "video"
    PHOTO = "photo"


@dataclass
class Config:
    """App configuration."""
    api_id: int = 0
    api_hash: str = ""
    datastore_url: str = ""
    
    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_id=int(os.getenv("TG_API_ID", "0")),
            api_hash=os.getenv("TG_API_HASH", ""),
            datastore_url=os.getenv("DATASTORE_API_URL", ""),
        )


@dataclass
class DownloadOptions:
    """Download options."""
    source: str
    limit: int = 100
    reverse: bool = False
    media_filter: MediaFilter = MediaFilter.ALL
    min_resolution: int | None = None
    min_duration: int | None = None
    dest_folder: str = "/Telegram"


# Paths
def config_dir() -> Path:
    path = Path.home() / ".config" / "tgup"
    path.mkdir(parents=True, exist_ok=True)
    return path

def session_path() -> Path:
    return config_dir() / "session"

def credentials_path() -> Path:
    return config_dir() / "credentials.json"

