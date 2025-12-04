"""Progress display with real progress bars."""
from rich.console import Console, Group
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TextColumn, SpinnerColumn
from rich.panel import Panel
from rich.text import Text

console = Console()


class Display:
    """Progress display with download/upload bars."""
    
    def __init__(self):
        self._download = Progress(
            SpinnerColumn(),
            TextColumn("[cyan]↓[/cyan]"),
            TextColumn("{task.fields[name]}", style="bold"),
            BarColumn(bar_width=25),
            DownloadColumn(),
            TransferSpeedColumn(),
            expand=False,
        )
        self._upload = Progress(
            SpinnerColumn(),
            TextColumn("[green]↑[/green]"),
            TextColumn("{task.fields[name]}", style="bold"),
            BarColumn(bar_width=25),
            DownloadColumn(),
            TransferSpeedColumn(),
            expand=False,
        )
        self._dl_task = None
        self._up_task = None
        
        self.uploaded = 0
        self.skipped = 0
        self.failed = 0
        self._logs: list[tuple[str, str]] = []
    
    def __rich__(self):
        """Render the display."""
        # Stats
        stats = Text()
        stats.append(f"✓ {self.uploaded} ", style="green bold")
        stats.append(f"⊘ {self.skipped} ", style="yellow bold")
        stats.append(f"✗ {self.failed}", style="red bold")
        
        # Logs
        logs = Text()
        for msg, style in self._logs[-3:]:
            logs.append(f"{msg}\n", style=style)
        
        return Group(
            Panel(self._download, title="Download", border_style="cyan", height=3),
            Panel(self._upload, title="Upload", border_style="green", height=3),
            stats,
            logs,
        )
    
    # Download progress
    def start_download(self, name: str, total: int):
        if self._dl_task is not None:
            self._download.remove_task(self._dl_task)
        self._dl_task = self._download.add_task("dl", total=total, name=name[:40])
    
    def update_download(self, current: int, total: int):
        if self._dl_task is not None:
            self._download.update(self._dl_task, completed=current, total=total)
    
    def finish_download(self):
        if self._dl_task is not None:
            try:
                task = self._download.tasks[self._dl_task]
                self._download.update(self._dl_task, completed=task.total)
            except (IndexError, KeyError):
                pass
    
    # Upload progress  
    def start_upload(self, name: str, total: int):
        if self._up_task is not None:
            self._upload.remove_task(self._up_task)
        self._up_task = self._upload.add_task("up", total=total, name=name[:40])
    
    def update_upload(self, current: int, total: int):
        if self._up_task is not None:
            self._upload.update(self._up_task, completed=current, total=total)
    
    def finish_upload(self, source_id: str):
        if self._up_task is not None:
            try:
                task = self._upload.tasks[self._up_task]
                self._upload.update(self._up_task, completed=task.total)
            except (IndexError, KeyError):
                pass
        self.uploaded += 1
        self._log(f"✓ {source_id}", "green")
    
    # Logging
    def skip(self, name: str, reason: str):
        self.skipped += 1
        if reason != "filter":
            self._log(f"⊘ {reason}: {name[:35]}", "yellow")
    
    def error(self, msg: str):
        self.failed += 1
        self._log(f"✗ {msg[:45]}", "red")
    
    def _log(self, msg: str, style: str = ""):
        self._logs.append((msg, style))
        if len(self._logs) > 10:
            self._logs = self._logs[-5:]
