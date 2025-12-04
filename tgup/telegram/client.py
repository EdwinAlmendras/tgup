"""Telegram client - connect and fetch media."""
import logging
from typing import AsyncIterator, Callable
from pathlib import Path
from telethon import TelegramClient as Telethon
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from FastTelethonhelper import fast_download
from ..config import session_path, MediaType, MediaFilter
from ..models import Media

log = logging.getLogger(__name__)
logging.getLogger("FastTelethon").setLevel(logging.WARNING)


class TelegramClient:
    """Telegram operations: connect, fetch, download."""
    
    def __init__(self, api_id: int, api_hash: str):
        self._client = Telethon(str(session_path()), api_id, api_hash)
    
    async def start(self) -> bool:
        """Start client, return True if authorized."""
        await self._client.connect()
        return await self._client.is_user_authorized()
    
    async def login(self, phone: str, code_cb: Callable, password_cb: Callable) -> bool:
        """Interactive login."""
        await self._client.start(phone=phone, code_callback=code_cb, password=password_cb)
        return await self._client.is_user_authorized()
    
    async def logout(self) -> None:
        """Logout and disconnect."""
        await self._client.log_out()
    
    async def close(self) -> None:
        """Close connection."""
        await self._client.disconnect()
    
    async def fetch_media(
        self, 
        source: str, 
        limit: int = 100,
        reverse: bool = False,
        media_filter: MediaFilter = MediaFilter.ALL
    ) -> AsyncIterator[Media]:
        """Fetch media from channel/chat."""
        entity = await self._client.get_entity(source)
        
        async for msg in self._client.iter_messages(entity, limit=limit, reverse=reverse):
            media = self._parse_message(msg)
            if media and self._matches_filter(media, media_filter):
                yield media
    
    def _parse_message(self, msg) -> Media | None:
        """Extract media from message."""
        if not msg.media:
            return None
        
        if isinstance(msg.media, MessageMediaPhoto):
            return Media(
                message_id=msg.id,
                chat_id=msg.chat_id,
                date=msg.date,
                media_type=MediaType.PHOTO,
                file_size=msg.media.photo.sizes[-1].size if msg.media.photo.sizes else 0,
            )
        
        if isinstance(msg.media, MessageMediaDocument):
            doc = msg.media.document
            attrs = {type(a).__name__: a for a in doc.attributes}
            
            is_video = "DocumentAttributeVideo" in attrs
            video_attr = attrs.get("DocumentAttributeVideo")
            filename_attr = attrs.get("DocumentAttributeFilename")
            
            return Media(
                message_id=msg.id,
                chat_id=msg.chat_id,
                date=msg.date,
                media_type=MediaType.VIDEO if is_video else MediaType.DOCUMENT,
                file_size=doc.size,
                filename=filename_attr.file_name if filename_attr else None,
                mime_type=doc.mime_type,
                width=video_attr.w if video_attr else None,
                height=video_attr.h if video_attr else None,
                duration=video_attr.duration if video_attr else None,
                document_id=str(doc.id),
            )
        return None
    
    def _matches_filter(self, media: Media, filter: MediaFilter) -> bool:
        """Check if media matches filter."""
        if filter == MediaFilter.ALL:
            return True
        if filter == MediaFilter.VIDEO:
            return media.media_type == MediaType.VIDEO
        if filter == MediaFilter.PHOTO:
            return media.media_type == MediaType.PHOTO
        return True
    
    async def download(
        self, 
        media: Media, 
        dest_dir: Path,
        progress_cb: Callable[[int, int], None] | None = None
    ) -> Path:
        """Download media using FastTelethon (parallel download)."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Target file path with proper name
        target_path = dest_dir / media.download_name
        
        msg = await self._client.get_messages(media.chat_id, ids=media.message_id)
        
        # Download to temp then rename (FastTelethon uses its own naming)
        temp_folder = str(dest_dir) + "/"
        
        downloaded_path = await fast_download(
            client=self._client,
            msg=msg,
            reply=None,
            download_folder=temp_folder,
            progress_callback=progress_cb,
        )
        
        # Rename to our naming convention
        downloaded = Path(downloaded_path)
        if downloaded.exists() and downloaded != target_path:
            downloaded.rename(target_path)
        
        log.info(f"Downloaded: {target_path.name}")
        return target_path

