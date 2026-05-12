"""
ui/tabs/project_tab.py

Project tab — load/save TOML, edit stock (including price per bar),
add/remove variables and parts.

Now inherits from ScrollableContainer so the full form is accessible
regardless of terminal height.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Input, Label, Static

from log import get_logger
from state.models import Part, Project, StockBar, Variable
from state.serialization import load as toml_load, save as toml_save, write_example
from ui.widgets.field_row import FieldRow
from ui.screens.project_browser import ProjectBrowserScreen
from ui.screens.add_variable import AddVariableScreen
from ui.screens.add_part import AddPartScreen

log = get_logger(__name__)


class ProjectTab(ScrollableContainer):
    """Project tab.  Scrollable so all fields are reachable on small terminals."""

    DEFAULT_CSS = """
    ProjectTab {
        padding: 1 2;
    }
    .section-heading {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    .status-bar {
        height: 1;
        color: $success;
        margin-top: 1;
    }
    #project-actions {
        height: 3;
        margin-bottom: 1;
    }
    #project-actions Button {
        margin-right: 1;
    }
    DataTable {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
    }
    """

    project:  reactive[Optional[Project]] = reactive(None)
    filepath: reactive[Optional[Path]]    = reactive(None)

    def compose(self) -> ComposeResult:
        yield Label("Cut-List Planner", classes="section-heading")
        yield Static("No project loaded.", id="project-status")

        with Horizontal(id="project-actions"):
            yield Button("Load TOML",   id="btn-load",       variant="primary")
            yield Button("Save",        id="btn-save",        variant="default")
            yield Button("New example", id="btn-new-example", variant="default")

        yield Label("Stock", classes="section-heading")
        yield FieldRow("Bar length (mm)", "stock-length", placeholder="6000")
        yield FieldRow("Width (mm)",      "stock-width",  placeholder="90")
        yield FieldRow("Height (mm)",     "stock-height", placeholder="45")
        yield FieldRow("Kerf (mm)",       "stock-kerf",   placeholder="3.0")
        yield FieldRow("Price / bar",     "stock-price",  placeholder="0.00")

        yield Label("Variables", classes="section-heading")
        yield DataTable(id="var-table", show_cursor=True)

        with Horizontal():
            yield Button("+ Variable", id="btn-add-var", variant="success")
            yield Button("– Remove",   id="btn-del-var", variant="error")

        yield Label("Parts", classes="section-heading")
        yield DataTable(id="part-table", show_cursor=True)

        with Horizontal():
            yield Button("+ Part",   id="btn-add-part", variant="success")
            yield Button("– Remove", id="btn-del-part", variant="error")

        yield Static("", id="proj-msg", classes="status-bar")

    def on_mount(self) -> None:
        self._init_tables()

    def _init_tables(self) -> None:
        vt: DataTable = self.query_one("#var-table")
        vt.clear(columns=True)
        vt.add_columns("Name", "Formula", "Resolved")

        pt: DataTable = self.query_one("#part-table")
        pt.clear(columns=True)
        pt.add_columns("Label", "Length expression", "Qty", "Length (mm)")

    # ------------------------------------------------------------------
    # Public API used by CutListApp and other tabs
    # ------------------------------------------------------------------

    def load_project(self, project: Project, filepath: Path | None = None) -> None:
        self.project  = project
        self.filepath = filepath
        self._refresh_ui()

    @property
    def price_per_bar(self) -> float:
        """Current value of the price-per-bar input field."""
        try:
            return float(self.query_one("#stock-price", Input).value or 0)
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_ui(self) -> None:
        p = self.project
        if p is None:
            return
        label = self.filepath.name if self.filepath else p.name
        self.query_one("#project-status", Static).update(
            f"[bold]{p.name}[/bold]  —  {label}  |  {p.stock.profile}  L={p.stock.length_mm:g} mm"
        )
        self.query_one("#stock-length", Input).value = str(p.stock.length_mm)
        self.query_one("#stock-width",  Input).value = str(p.stock.width_mm)
        self.query_one("#stock-height", Input).value = str(p.stock.height_mm)
        self.query_one("#stock-kerf",   Input).value = str(p.stock.kerf_mm)

        try:
            scope = p.resolve_all()
        except Exception:
            scope = {}

        vt: DataTable = self.query_one("#var-table")
        vt.clear()
        for v in p.variables:
            resolved = f"{scope.get(v.name, '?'):.3f}" if v.name in scope else "?"
            vt.add_row(v.name, v.formula, resolved)

        pt: DataTable = self.query_one("#part-table")
        pt.clear()
        for part in p.parts:
            length_val = f"{part.length_mm:.1f}" if part.length_mm else "?"
            pt.add_row(part.label, part.length_expr, str(part.quantity), length_val)

    def _collect_project(self) -> Project | None:
        try:
            length_mm = float(self.query_one("#stock-length", Input).value or 6000)
            width_mm  = float(self.query_one("#stock-width",  Input).value or 50)
            height_mm = float(self.query_one("#stock-height", Input).value or 50)
            kerf_mm   = float(self.query_one("#stock-kerf",   Input).value or 3.0)
        except ValueError:
            self._msg("Invalid stock values.", error=True)
            return None
        if self.project is None:
            return None
        return Project(
            name=self.project.name,
            stock=StockBar(
                length_mm=length_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                kerf_mm=kerf_mm,
            ),
            variables=list(self.project.variables),
            parts=list(self.project.parts),
        )

    def _msg(self, text: str, error: bool = False) -> None:
        colour = "red" if error else "green"
        self.query_one("#proj-msg", Static).update(f"[{colour}]{text}[/{colour}]")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#btn-load")
    def handle_load(self) -> None:
        self.app.push_screen(ProjectBrowserScreen("load"), self._on_load)

    def _on_load(self, path: str | None) -> None:
        if not path:
            return
        try:
            p = toml_load(path)
            self.load_project(p, Path(path))
            self.app.notify(f"Loaded: {path}", title="Project")
            log.info("Project loaded: %s  (%d variables, %d parts)",
                     path, len(p.variables), len(p.parts))
            self.app.on_project_loaded(p)
        except Exception as exc:
            log.exception("Failed to load project from %s", path)
            self._msg(str(exc), error=True)

    @on(Button.Pressed, "#btn-save")
    def handle_save(self) -> None:
        p = self._collect_project()
        if p is None:
            return
        if self.filepath:
            toml_save(p, self.filepath)
            self._msg(f"Saved → {self.filepath.name}")
        else:
            self.app.push_screen(ProjectBrowserScreen("save"), self._on_save)

    def _on_save(self, path: str | None) -> None:
        if not path:
            return
        p = self._collect_project()
        if p:
            toml_save(p, path)
            self.filepath = Path(path)
            log.info("Project saved: %s", path)
            self._msg(f"Saved → {path}")

    @on(Button.Pressed, "#btn-new-example")
    def handle_new_example(self) -> None:
        self.app.push_screen(ProjectBrowserScreen("save"), self._on_example)

    def _on_example(self, path: str | None) -> None:
        if not path:
            return
        write_example(path)
        try:
            p = toml_load(path)
            self.load_project(p, Path(path))
            self.app.on_project_loaded(p)
            self._msg(f"Example written and loaded: {path}")
        except Exception as exc:
            self._msg(str(exc), error=True)

    @on(Button.Pressed, "#btn-add-var")
    def handle_add_var(self) -> None:
        self.app.push_screen(AddVariableScreen(), self._on_add_var)

    def _on_add_var(self, result: tuple[str, str] | None) -> None:
        if result is None or self.project is None:
            return
        name, formula = result
        self.project.variables.append(Variable(name=name, formula=formula))
        self._refresh_ui()

    @on(Button.Pressed, "#btn-del-var")
    def handle_del_var(self) -> None:
        if self.project is None:
            return
        vt: DataTable = self.query_one("#var-table")
        row = vt.cursor_row
        if 0 <= row < len(self.project.variables):
            self.project.variables.pop(row)
            self._refresh_ui()

    @on(Button.Pressed, "#btn-add-part")
    def handle_add_part(self) -> None:
        self.app.push_screen(AddPartScreen(), self._on_add_part)

    def _on_add_part(self, result: tuple[str, str, int] | None) -> None:
        if result is None or self.project is None:
            return
        label, expr, qty = result
        self.project.parts.append(Part(label=label, length_expr=expr, quantity=qty))
        self._refresh_ui()

    @on(Button.Pressed, "#btn-del-part")
    def handle_del_part(self) -> None:
        if self.project is None:
            return
        pt: DataTable = self.query_one("#part-table")
        row = pt.cursor_row
        if 0 <= row < len(self.project.parts):
            self.project.parts.pop(row)
            self._refresh_ui()
