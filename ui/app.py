"""
ui/app.py

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
        Binding("f1",     "tab_project", "Project"),
        Binding("f2",     "tab_results", "Results"),
        Binding("f3",     "tab_sweep",   "Sweep"),
    ]

    def __init__(self, project_path: str | None = None) -> None:
        super().__init__()
        self._initial_path = project_path

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="main-tabs"):
            with TabPane("Project [F1]", id="tab-project"):
                yield ProjectTab()
            with TabPane("Results [F2]", id="tab-results"):
                yield ResultsTab()
            with TabPane("Sweep [F3]",   id="tab-sweep"):
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
