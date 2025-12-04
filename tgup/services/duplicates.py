"""Duplicate checking service."""
import logging
import httpx
from typing import Set

log = logging.getLogger(__name__)


class DuplicateChecker:
    """Check if media was already processed."""
    
    def __init__(self, api_url: str | None = None):
        self._api_url = api_url
        self._known_ids: Set[str] = set()
    
    async def load(self) -> int:
        """Load known IDs from API. Returns count."""
        if not self._api_url:
            return 0
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._api_url}/telegram/ids", timeout=30)
                resp.raise_for_status()
                data = resp.json()
                self._known_ids = set(data.get("ids", []))
                log.info(f"Loaded {len(self._known_ids)} document IDs")
                return len(self._known_ids)
        except Exception as e:
            log.warning(f"Failed to load IDs: {e}")
            return 0
    
    def is_duplicate(self, document_id: str) -> bool:
        """Check if document ID is known."""
        return document_id in self._known_ids
    
    def add(self, document_id: str) -> None:
        """Add ID to known set."""
        self._known_ids.add(document_id)
    
    @property
    def count(self) -> int:
        return len(self._known_ids)

