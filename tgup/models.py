"""Data models - pure data, no logic."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from .config import MediaType


@dataclass(frozen=True)
class Media:
    """Telegram media metadata."""
    message_id: int
    chat_id: int
    date: datetime
    media_type: MediaType
    file_size: int = 0
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    document_id: str | None = None
    
    @property
    def download_name(self) -> str:
        """Generate download filename."""
        date_str = self.date.strftime("%d%m%Y")
        base = f"{self.message_id}_{date_str}"
        if self.filename:
            return f"{base}_{self.filename}"
        ext = ".mp4" if self.media_type == MediaType.VIDEO else ".jpg"
        return f"{base}{ext}"


@dataclass
class DownloadResult:
    """Download operation result."""
    success: bool
    file_path: Path | None = None
    error: str | None = None


@dataclass
class UploadResult:
    """Upload operation result."""
    success: bool
    source_id: str | None = None
    error: str | None = None

