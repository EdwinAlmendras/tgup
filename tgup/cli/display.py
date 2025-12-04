"""Progress display - simple and clean."""
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.console import Console

console = Console()


class Display:
    """Simple progress display."""
    
    def __init__(self):
        self.current = ""
        self.uploaded = 0
        self.skipped = 0
        self.failed = 0
        self._logs: list[tuple[str, str]] = []
    
    def __rich__(self):
        """Render display."""
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(width=50)
        
        # Stats row
        stats = Text()
        stats.append(f"✓ {self.uploaded} ", style="green")
        stats.append(f"⊘ {self.skipped} ", style="yellow")
        stats.append(f"✗ {self.failed}", style="red")
        tbl.add_row(stats)
        
        # Current operation
        if self.current:
            tbl.add_row(Text(f"▶ {self.current[:45]}", style="cyan"))
        
        # Recent logs
        for msg, style in self._logs[-4:]:
            tbl.add_row(Text(msg, style=style))
        
        return tbl
    
    def set_current(self, name: str):
        self.current = name
    
    def log(self, msg: str, style: str = ""):
        self._logs.append((msg, style))
        if len(self._logs) > 10:
            self._logs = self._logs[-5:]
    
    def log_upload(self, source_id: str):
        self.uploaded += 1
        self.log(f"✓ {source_id}", "green")
    
    def log_skip(self, name: str, reason: str):
        self.skipped += 1
        if reason != "filter":
            self.log(f"⊘ {reason}: {name[:35]}", "yellow")
    
    def log_error(self, msg: str):
        self.failed += 1
        self.log(f"✗ {msg[:40]}", "red")

