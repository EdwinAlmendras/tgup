"""Pipeline - orchestrates download and upload."""
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from .config import DownloadOptions, config_dir
from .models import Media
from .telegram import TelegramClient
from .services import DuplicateChecker

log = logging.getLogger(__name__)


@dataclass
class Stats:
    """Pipeline statistics."""
    total: int = 0
    downloaded: int = 0
    uploaded: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class PipelineCallbacks:
    """Progress callbacks."""
    on_start: Callable[[Media], None] | None = None
    on_download: Callable[[Media], None] | None = None
    on_upload: Callable[[Media, str], None] | None = None
    on_skip: Callable[[Media, str], None] | None = None
    on_error: Callable[[Media, str], None] | None = None
    on_download_progress: Callable[[int, int], None] | None = None
    on_upload_progress: Callable[[int, int], None] | None = None


class Pipeline:
    """Download from Telegram, upload to MEGA."""
    
    def __init__(
        self,
        tg_client: TelegramClient,
        mega_manager,
        uploader,
        options: DownloadOptions,
        duplicates: DuplicateChecker | None = None,
        callbacks: PipelineCallbacks | None = None,
    ):
        self._tg = tg_client
        self._mega = mega_manager
        self._uploader = uploader
        self._options = options
        self._duplicates = duplicates
        self._cb = callbacks or PipelineCallbacks()
        self._existing: set[str] = set()
        self.stats = Stats()
    
    async def run(self) -> Stats:
        """Run the pipeline."""
        await self._load_existing_files()
        if self._duplicates:
            await self._duplicates.load()
        
        queue: asyncio.Queue = asyncio.Queue()
        upload_task = asyncio.create_task(self._upload_worker(queue))
        
        async for media in self._tg.fetch_media(
            self._options.source,
            self._options.limit,
            self._options.reverse,
            self._options.media_filter,
        ):
            self.stats.total += 1
            
            # Skip by filter
            if self._should_skip(media):
                self.stats.skipped += 1
                self._notify("on_skip", media, "filter")
                continue
            
            # Skip duplicates
            if self._duplicates and media.document_id:
                if self._duplicates.is_duplicate(media.document_id):
                    self.stats.skipped += 1
                    self._notify("on_skip", media, "duplicate")
                    continue
            
            # Skip existing in MEGA (checks all accounts)
            if await self._file_exists_in_mega(media.download_name):
                self.stats.skipped += 1
                self._notify("on_skip", media, "exists")
                continue
            
            # Download and queue
            self._notify("on_start", media)
            try:
                progress_cb = None
                if self._cb.on_download_progress:
                    progress_cb = lambda c, t: self._cb.on_download_progress(c, t)
                file_path = await self._tg.download(media, config_dir() / "downloads", progress_cb)
                self.stats.downloaded += 1
                self._notify("on_download", media)
                await queue.put((media, file_path))
            except Exception as e:
                self.stats.failed += 1
                self._notify("on_error", media, str(e))
                log.error(f"Download failed: {e}")
        
        await queue.put(None)  # Signal end
        await upload_task
        return self.stats
    
    async def _upload_worker(self, queue: asyncio.Queue):
        """Upload files from queue."""
        while True:
            item = await queue.get()
            if item is None:
                break
            
            media, file_path = item
            try:
                result = await self._upload_file(media, file_path)
                if result:
                    self.stats.uploaded += 1
                    self._existing.add(media.download_name)
                    if self._duplicates and media.document_id:
                        self._duplicates.add(media.document_id)
                    self._notify("on_upload", media, result)
                else:
                    self.stats.failed += 1
            except Exception as e:
                self.stats.failed += 1
                self._notify("on_error", media, str(e))
                log.error(f"Upload failed: {e}")
            finally:
                file_path.unlink(missing_ok=True)
    
    async def _upload_file(self, media: Media, file_path: Path) -> str | None:
        """Upload single file, return source_id."""
        from uploader import TelegramInfo
        
        info = TelegramInfo(
            message_id=media.message_id,
            chat_id=media.chat_id,
            upload_date=media.date.isoformat(),
            telegram_document_id=media.document_id,
        )
        
        progress_cb = None
        if self._cb.on_upload_progress:
            def progress_cb(p):
                self._cb.on_upload_progress(p.uploaded_bytes, p.total_bytes)
        
        result = await self._uploader.upload_telegram(
            file_path,
            telegram_info=info,
            dest=self._options.dest_folder,
            progress_callback=progress_cb,
        )
        return result.source_id if result.success else None
    
    async def _load_existing_files(self):
        """Load existing filenames from MEGA (all accounts)."""
        try:
            if hasattr(self._mega, 'list_all'):
                items = await self._mega.list_all(self._options.dest_folder)
                self._existing = {node.name for _, node in items}
                log.info(f"Found {len(self._existing)} existing files")
        except Exception as e:
            log.warning(f"Could not load existing files: {e}")
    
    async def _file_exists_in_mega(self, filename: str) -> bool:
        """Check if file exists in any MEGA account."""
        # First check cache
        if filename in self._existing:
            return True
        
        # Then check via API (slower but catches files added during run)
        full_path = f"{self._options.dest_folder}/{filename}"
        try:
            if hasattr(self._mega, 'exists'):
                if await self._mega.exists(full_path):
                    self._existing.add(filename)
                    return True
        except Exception:
            pass
        return False
    
    def _should_skip(self, media: Media) -> bool:
        """Check filter criteria."""
        opts = self._options
        if opts.min_resolution and media.width and media.height:
            if min(media.width, media.height) < opts.min_resolution:
                return True
        if opts.min_duration and media.duration:
            if media.duration < opts.min_duration:
                return True
        return False
    
    def _notify(self, event: str, *args):
        """Call callback if set."""
        cb = getattr(self._cb, event, None)
        if cb:
            try:
                cb(*args)
            except Exception:
                pass

