"""Telegram session management."""
import json
import logging
from pathlib import Path
from ..config import session_path, credentials_path

log = logging.getLogger(__name__)


class TelegramSession:
    """Manages Telegram session and credentials."""
    
    def save_credentials(self, api_id: int, api_hash: str) -> None:
        """Save API credentials."""
        data = {"api_id": api_id, "api_hash": api_hash}
        credentials_path().write_text(json.dumps(data))
        log.info("Credentials saved")
    
    def load_credentials(self) -> tuple[int, str]:
        """Load API credentials."""
        path = credentials_path()
        if not path.exists():
            return 0, ""
        try:
            data = json.loads(path.read_text())
            return data.get("api_id", 0), data.get("api_hash", "")
        except Exception as e:
            log.warning(f"Failed to load credentials: {e}")
            return 0, ""
    
    def get_session_file(self) -> Path:
        """Get session file path."""
        return session_path()
    
    def exists(self) -> bool:
        """Check if session exists."""
        return session_path().with_suffix(".session").exists()
    
    def delete(self) -> None:
        """Delete session and credentials."""
        session = session_path().with_suffix(".session")
        creds = credentials_path()
        if session.exists():
            session.unlink()
        if creds.exists():
            creds.unlink()
        log.info("Session deleted")

