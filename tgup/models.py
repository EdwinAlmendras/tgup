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
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    document_id: str | None = None
    
    @property
    def download_name(self) -> str:
        """Generate filename: original name or {date}_{time}.ext"""
        if self.filename:
            return self.filename
            
        date_str = self.date.strftime("%Y%m%d_%H%M%S")
        return f"{date_str}{self._guess_ext()}"
    
    def _guess_ext(self) -> str:
        """Guess extension from mime or type."""
        if self.mime_type:
            ext_map = {
                "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
                "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
            }
            return ext_map.get(self.mime_type, ".mp4")
        
        return ".mp4" if self.media_type == MediaType.VIDEO else ".jpg"


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

