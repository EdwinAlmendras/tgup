"""CLI commands - thin layer, delegates to services."""
import logging
from typing import Union
import typer
from pathlib import Path
from rich.console import Console
from rich.live import Live
from .display import Display
from ..config import Config, DownloadOptions, MediaFilter
from ..telegram import TelegramClient, TelegramSession
from ..services import DuplicateChecker
from ..pipeline import Pipeline, PipelineCallbacks

# Silence noisy loggers
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("megapy").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

app = typer.Typer(help="Telegram to MEGA uploader")
console = Console()


@app.command()
def login(
    api_id: int = typer.Option(..., "--api-id", "-i", envvar="TG_API_ID"),
    api_hash: str = typer.Option(..., "--api-hash", "-h", envvar="TG_API_HASH"),
    phone: str = typer.Option(..., "--phone", "-p"),
):
    """Login to Telegram."""
    import asyncio
    
    async def do_login():
        session = TelegramSession()
        session.save_credentials(api_id, api_hash)
        
        client = TelegramClient(api_id, api_hash)
        code_cb = lambda: typer.prompt("Code")
        pass_cb = lambda: typer.prompt("2FA Password", hide_input=True)
        
        if await client.login(phone, code_cb, pass_cb):
            console.print("[green]✓ Logged in[/green]")
        else:
            console.print("[red]Login failed[/red]")
        await client.close()
    
    asyncio.get_event_loop().run_until_complete(do_login())


@app.command()
def logout():
    """Logout and delete session."""
    TelegramSession().delete()
    console.print("[green]✓ Logged out[/green]")


@app.command()
def status():
    """Check login status."""
    session = TelegramSession()
    if session.exists():
        console.print("[green]✓ Logged in[/green]")
    else:
        console.print("[yellow]Not logged in[/yellow]")


@app.command("up")
def upload(
    source: str = typer.Argument(..., help="Channel/chat"),
    limit: int = typer.Option(100, "-l", "--limit"),
    reverse: bool = typer.Option(False, "-r", "--reverse"),
    filter_type: str = typer.Option("all", "-f", "--filter", help="all/video/photo"),
    min_res: int = typer.Option(0, "--min-res"),
    min_dur: int = typer.Option(0, "--min-dur"),
    flat: bool = typer.Option(False, "--flat"),
):
    """Download from Telegram, upload to MEGA."""
    import asyncio
    import os
    
    async def do_upload():
        nonlocal source
        try:
            source = int(source)
        except ValueError:
            pass
        from uploader import UploadOrchestrator, ManagedStorageService
        
        # Load config
        session = TelegramSession()
        api_id, api_hash = session.load_credentials()
        api_url = os.getenv("DATASTORE_API_URL")
        
        if not api_id:
            console.print("[red]Not logged in. Run: tgup login[/red]")
            raise typer.Exit(1)
        
        # Connect Telegram
        tg = TelegramClient(api_id, api_hash)
        if not await tg.start():
            console.print("[red]Session expired. Run: tgup login[/red]")
            raise typer.Exit(1)
        storage = ManagedStorageService()
        await storage.check_accounts_space()
        # Options
        media_filter = {
            "all": MediaFilter.ALL, 
            "video": MediaFilter.VIDEO, "videos": MediaFilter.VIDEO,
            "photo": MediaFilter.PHOTO, "photos": MediaFilter.PHOTO,
        }
        entity = await tg._client.get_entity(source)
        
        def get_properly_name(entity):
            if getattr(entity, 'username', None):
                return entity.username
            elif getattr(entity, 'title', None):
                return entity.title
            else:
                return str(entity.id)
        
        channel = get_properly_name(entity)
        dest = "/Telegram" if flat else f"/Telegram/{channel}"
        
        options = DownloadOptions(
            source=source,
            limit=limit,
            reverse=reverse,
            media_filter=media_filter.get(filter_type, MediaFilter.ALL),
            min_resolution=min_res,
            min_duration=min_dur,
            dest_folder=dest,
        )
        
        console.print(f"[cyan]Source:[/cyan] {source}")
        console.print(f"[cyan]Dest:[/cyan] {dest}")
        
        # Display with progress callbacks
        display = Display()
        
        callbacks = PipelineCallbacks(
            on_start=lambda m: display.start_download(m.download_name, m.file_size or 0),
            on_download=lambda m: (display.finish_download(), display.start_upload(m.download_name, m.file_size or 0)),
            on_upload=lambda m, sid: display.finish_upload(sid),
            on_skip=lambda m, r: display.skip(m.download_name, r),
            on_error=lambda m, e: display.error(e),
            on_download_progress=lambda c, t: display.update_download(c, t),
            on_upload_progress=lambda c, t: display.update_upload(c, t),
        )
        
        try:
            async with UploadOrchestrator(api_url, storage_service=storage) as uploader:
                pipeline = Pipeline(
                    tg_client=tg,
                    mega_manager=storage.manager,
                    uploader=uploader,
                    options=options,
                    duplicates=DuplicateChecker(api_url),
                    callbacks=callbacks,
                )
                
                with Live(display, refresh_per_second=2, console=console):
                    stats = await pipeline.run()
                
                console.print(f"\n[cyan]Done:[/cyan] {stats.uploaded} uploaded, {stats.skipped} skipped, {stats.failed} failed")
        finally:
            await tg.close()
            await storage.close()
    
    asyncio.get_event_loop().run_until_complete(do_upload())


def main():
    app()


if __name__ == "__main__":
    main()

