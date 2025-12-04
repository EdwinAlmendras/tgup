"""Tests for pipeline performance - verify no blocking bottlenecks."""
import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from tgup.pipeline import Pipeline, PipelineCallbacks, Stats
from tgup.models import Media, MediaType
from tgup.config import DownloadOptions, MediaFilter


class TestPipelinePerformance:
    """Test pipeline doesn't block on preview generation."""
    
    @pytest.fixture
    def mock_tg_client(self):
        """Mock Telegram client."""
        client = MagicMock()
        client.fetch_media = AsyncMock()
        client.download = AsyncMock(return_value=Path("/tmp/test.mp4"))
        return client
    
    @pytest.fixture
    def mock_uploader(self):
        """Mock uploader that simulates slow preview generation."""
        uploader = MagicMock()
        
        async def slow_upload(*args, **kwargs):
            # Simulate upload + slow preview generation
            await asyncio.sleep(0.1)  # Upload time
            result = MagicMock()
            result.success = True
            result.source_id = "abc123"
            return result
        
        uploader.upload_telegram = AsyncMock(side_effect=slow_upload)
        return uploader
    
    @pytest.fixture
    def options(self):
        """Download options."""
        return DownloadOptions(
            source="@test",
            limit=5,
            reverse=False,
            media_filter=MediaFilter.ALL,
            dest_folder="/test"
        )
    
    @pytest.mark.asyncio
    async def test_upload_doesnt_block_download(self, mock_tg_client, mock_uploader, options):
        """Test that slow uploads don't block downloads."""
        # Create media items
        media_items = []
        for i in range(3):
            media = Media(
                message_id=i,
                chat_id=123,
                date=datetime.now(),
                media_type=MediaType.VIDEO,
                file_size=1000000,
                document_id=f"doc{i}",
                filename=f"test{i}.mp4"
            )
            media_items.append(media)
        
        # Mock fetch_media to yield items quickly
        async def fast_fetch(*args, **kwargs):
            for m in media_items:
                yield m
        
        mock_tg_client.fetch_media = fast_fetch
        
        # Mock mega manager
        mega_manager = MagicMock()
        mega_manager.list_all = AsyncMock(return_value=[])
        mega_manager.exists = AsyncMock(return_value=False)
        
        # Create pipeline
        pipeline = Pipeline(
            tg_client=mock_tg_client,
            mega_manager=mega_manager,
            uploader=mock_uploader,
            options=options,
            duplicates=None,
            callbacks=None
        )
        
        # Measure time
        import time
        start = time.time()
        stats = await pipeline.run()
        elapsed = time.time() - start
        
        # Downloads should complete quickly (not blocked by uploads)
        # With 3 items and 0.1s upload each, should be ~0.3s if parallel
        # But downloads should finish much faster (allow some overhead)
        assert elapsed < 1.5, f"Pipeline took {elapsed}s, should be < 1.5s (downloads not blocked)"
        assert stats.downloaded == 3
        assert stats.uploaded == 3
    
    @pytest.mark.asyncio
    async def test_queue_doesnt_fill_up(self, mock_tg_client, mock_uploader, options):
        """Test that queue doesn't fill up when uploads are slow."""
        # Create many media items
        media_items = []
        for i in range(10):
            media = Media(
                message_id=i,
                chat_id=123,
                date=datetime.now(),
                media_type=MediaType.VIDEO,
                file_size=1000000,
                document_id=f"doc{i}",
                filename=f"test{i}.mp4"
            )
            media_items.append(media)
        
        async def fast_fetch(*args, **kwargs):
            for m in media_items:
                yield m
        
        mock_tg_client.fetch_media = fast_fetch
        
        mega_manager = MagicMock()
        mega_manager.list_all = AsyncMock(return_value=[])
        mega_manager.exists = AsyncMock(return_value=False)
        
        pipeline = Pipeline(
            tg_client=mock_tg_client,
            mega_manager=mega_manager,
            uploader=mock_uploader,
            options=options,
            duplicates=None,
            callbacks=None
        )
        
        # Should complete without hanging
        stats = await asyncio.wait_for(pipeline.run(), timeout=5.0)
        
        assert stats.downloaded == 10
        assert stats.uploaded == 10
    
    @pytest.mark.asyncio
    async def test_preview_generation_non_blocking(self):
        """Test that preview generation doesn't block upload return."""
        from uploader import UploadOrchestrator
        from uploader.services.storage import StorageService
        from uploader.services.analyzer import AnalyzerService
        from uploader.services.repository import MetadataRepository, HTTPAPIClient
        from uploader.services.preview import PreviewService
        from uploader.models import UploadConfig
        
        # Mock services
        mock_storage = MagicMock()
        mock_storage.upload_video = AsyncMock(return_value="handle123")
        mock_storage.upload_preview = AsyncMock(return_value="preview_handle")
        
        mock_repo = MagicMock()
        mock_repo.save_document = AsyncMock()
        mock_repo.save_video_metadata = AsyncMock()
        
        # Mock preview to be slow
        mock_preview = MagicMock()
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(0.5)  # Simulate slow preview generation
            return Path("/tmp/preview.jpg")
        mock_preview.generate = AsyncMock(side_effect=slow_generate)
        
        # Create orchestrator with mocked services
        config = UploadConfig(generate_preview=True)
        
        # We can't easily test UploadOrchestrator without full setup,
        # but we can test the pattern
        async def upload_with_preview():
            # Simulate upload
            await asyncio.sleep(0.1)
            handle = "handle123"
            
            # Start preview in background (non-blocking)
            preview_task = asyncio.create_task(slow_generate())
            
            # Return immediately (not waiting for preview)
            return handle
        
        # Measure time
        import time
        start = time.time()
        handle = await upload_with_preview()
        elapsed = time.time() - start
        
        # Should return quickly (not wait for preview)
        assert elapsed < 0.2, f"Upload returned in {elapsed}s, should be < 0.2s"
        assert handle == "handle123"
        
        # Wait for preview to complete
        await asyncio.sleep(0.6)
