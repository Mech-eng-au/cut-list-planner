"""
CutListApp — the Textual application root.

Mounts the three tabs (Project, Results, Sweep) inside a TabbedContent
widget and wires them together via on_project_loaded() and price_per_bar.

All tab logic lives in ui/tabs/*.  This module contains only:
    - App-level CSS / BINDINGS
    - compose() / on_mount()
    - Cross-tab wiring helpers
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from log import get_logger
from state.models import Project
from state.serialization import load as toml_load

from ui.tabs.project_tab import ProjectTab
from ui.tabs.results_tab import ResultsTab
from ui.tabs.sweep_tab   import SweepTab

log = get_logger(__name__)


class CutListApp(App):
    """The Cut-List Planner TUI application."""

    TITLE     = "Cut-List Planner"
    SUB_TITLE = "parametric steel cutting optimizer"

    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit",        "Quit"),
        Binding("ctrl+s", "save",        "Save"),
        Binding("ctrl+tab", "next_tab", "Next Tab"),
        Binding("ctrl+shift+tab", "prev_tab", "Previous Tab"),
        Binding("f1",     "tab_project", "📁 Project"),
        Binding("f2",     "tab_results", "📊 Results"),
        Binding("f3",     "tab_sweep",   "🔄 Sweep"),
        Binding("f12",    "help",        "Help"),
    ]

    def __init__(self, project_path: str | None = None) -> None:
        super().__init__()
        self._initial_path = project_path

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="main-tabs"):
            with TabPane("📁 Project [F1]", id="tab-project"):
                yield ProjectTab()
            with TabPane("📊 Results [F2]", id="tab-results"):
                yield ResultsTab()
            with TabPane("🔄 Sweep [F3]",   id="tab-sweep"):
                yield SweepTab()
        yield Footer()

    def on_mount(self) -> None:
        log.info("CutListApp mounted")
        if self._initial_path:
            try:
                p = toml_load(self._initial_path)
                self.query_one(ProjectTab).load_project(p, Path(self._initial_path))
                self.on_project_loaded(p)
                self.notify(f"Loaded: {self._initial_path}", title="Project")
                log.info("Initial project loaded from CLI arg: %s", self._initial_path)
            except Exception as exc:
                log.exception("Failed to load initial project: %s", self._initial_path)
                self.notify(str(exc), title="Load error", severity="error")

    # ------------------------------------------------------------------
    # Cross-tab wiring
    # ------------------------------------------------------------------

    def on_project_loaded(self, project: Project) -> None:
        """Called by ProjectTab after a project is loaded or created."""
        self.query_one(ResultsTab).set_project(project)
        self.query_one(SweepTab).set_project(project)

    @property
    def price_per_bar(self) -> float:
        """Delegates to ProjectTab so the Results worker can read it."""
        return self.query_one(ProjectTab).price_per_bar

    # ------------------------------------------------------------------
    # Key-binding actions
    # ------------------------------------------------------------------

    def action_save(self) -> None:
        self.query_one(ProjectTab).handle_save()

    def action_tab_project(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-project"

    def action_tab_results(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-results"

    def action_tab_sweep(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tab-sweep"

    def action_next_tab(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        current_index = tabs.panes.index(tabs.active_pane)
        next_index = (current_index + 1) % len(tabs.panes)
        tabs.active = tabs.panes[next_index].id

    def action_prev_tab(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        current_index = tabs.panes.index(tabs.active_pane)
        prev_index = (current_index - 1) % len(tabs.panes)
        tabs.active = tabs.panes[prev_index].id

    def action_help(self) -> None:
        help_text = """
[bold]Cut-List Planner Help[/bold]

[dim]Navigation:[/dim]
  [bold]Ctrl+Tab[/bold]    : Next Tab
  [bold]Ctrl+Shift+Tab[/bold] : Previous Tab
  [bold]F1[/bold]         : 📁 Project Tab
  [bold]F2[/bold]         : 📊 Results Tab
  [bold]F3[/bold]         : 🔄 Sweep Tab

[dim]Actions:[/dim]
  [bold]Ctrl+S[/bold]     : Save Project
  [bold]Ctrl+Q[/bold]     : Quit

[dim]Tips:[/dim]
  Use [bold]Tab[/bold] to navigate between input fields.
  Press [bold]Esc[/bold] to clear selections or close dialogs.
        """
        self.push_screen(HelpScreen(help_text))


class HelpScreen(App.Screen):
    """A simple help screen for CutListApp."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
        background: $background;
        color: $text;
    }
    
    HelpScreen > Static {
        width: 80%;
        height: 80%;
        background: $secondary;
        color: white;
        border: solid $primary;
        padding: 2;
        overflow-y: auto;
    }
    """

    def __init__(self, help_text: str):
        super().__init__()
        self.help_text = help_text

    def compose(self) -> ComposeResult:
        yield Static(self.help_text, id="help-content")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
