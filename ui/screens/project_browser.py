"""
Modal file browser scoped to the projects/ folder.
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label

from state.serialization import write_example

# The projects/ folder sits one level above the ui/ package.
_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class ProjectBrowserScreen(ModalScreen[str | None]):
    """
    Modal file browser scoped to projects/.

    Arrow keys / click navigate the file list.
    Enter on a list row OR clicking Open confirms selection.
    Typing in the path box overrides the list selection.

    Dismissed with the chosen path string, or None on cancel.
    """

    DEFAULT_CSS = """
    ProjectBrowserScreen { align: center middle; }
    #dialog {
        width: 70;
        height: 24;
        border: thick $accent;
        background: $secondary;
        padding: 1 2;
    }
    #browser-title {
        text-style: bold;
        color: $accent;
        height: 1;
        margin-bottom: 1;
    }
    #projects-label {
        color: $text;
        height: 1;
        margin-bottom: 0;
    }
    #projects-list {
        height: 10;
        border: tall $primary;
        margin-bottom: 1;
    }
    #projects-list .datatable--header {
        background: $secondary;
        color: white;
        text-style: bold;
    }
    #projects-list .datatable--row:focus {
        background: $primary;
        color: white;
    }
    #path-label {
        color: $text;
        height: 1;
        margin-top: 1;
        margin-bottom: 0;
    }
    #file-path-input {
        margin-bottom: 1;
        background: $background;
        color: $text;
        border: solid $primary;
    }
    #file-path-input:focus {
        border: solid $accent;
    }
    #browser-actions Button {
        margin-right: 1;
    }
    Button.primary {
        background: $primary;
        color: white;
        border: solid $primary;
    }
    Button:hover {
        opacity: 0.8;
    }
    """

    def __init__(self, mode: str = "load") -> None:
        super().__init__()
        self._mode       = mode
        self._toml_files: list[Path] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(
                "Open project" if self._mode == "load" else "Save project",
                id="browser-title",
            )
            yield Label(f"📁  {_PROJECTS_DIR}", id="projects-label")
            yield DataTable(
                id="projects-list",
                show_cursor=True,
                cursor_type="row",
                show_header=False,
            )
            yield Label("Or type any path:", id="path-label")
            yield Input(placeholder="path/to/project.toml", id="file-path-input")
            with Horizontal(id="browser-actions"):
                yield Button("Open",        id="btn-ok",      variant="primary")
                yield Button("New example", id="btn-example", variant="default")
                yield Button("Cancel",      id="btn-cancel",  variant="default")

    def on_mount(self) -> None:
        self._refresh_list()
        if self._toml_files:
            self.query_one("#projects-list").focus()
        else:
            self.query_one("#file-path-input").focus()

    def _refresh_list(self) -> None:
        table: DataTable = self.query_one("#projects-list")
        table.clear(columns=True)
        table.add_column("filename", width=60)
        _PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        self._toml_files = sorted(_PROJECTS_DIR.glob("*.toml"))
        if self._toml_files:
            for p in self._toml_files:
                table.add_row(p.name)
        else:
            table.add_row("(no .toml files yet — click 'New example' to create one)")
            self._toml_files = []

    def _selected_path(self) -> str | None:
        typed = self.query_one("#file-path-input", Input).value.strip()
        if typed:
            return typed
        table: DataTable = self.query_one("#projects-list")
        row = table.cursor_row
        if self._toml_files and 0 <= row < len(self._toml_files):
            return str(self._toml_files[row])
        return None

    @on(Button.Pressed, "#btn-ok")
    def confirm(self) -> None:
        self.dismiss(self._selected_path())

    @on(Button.Pressed, "#btn-example")
    def create_example(self) -> None:
        _PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        dest = _PROJECTS_DIR / "braced_frame.toml"
        write_example(str(dest))
        self._refresh_list()
        self.app.notify(f"Created {dest.name}", title="Example project")

    @on(Button.Pressed, "#btn-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(DataTable.RowSelected, "#projects-list")
    def row_selected(self, event: DataTable.RowSelected) -> None:
        self.dismiss(self._selected_path())

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter" and self.query_one("#file-path-input").has_focus:
            self.dismiss(self._selected_path())
