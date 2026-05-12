"""
ui/screens/add_variable.py

Modal screen for adding a new Variable to the project.
Dismissed with (name, formula) on confirm, or None on cancel.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from ui.widgets.field_row import FieldRow


class AddVariableScreen(ModalScreen[tuple[str, str] | None]):
    DEFAULT_CSS = """
    AddVariableScreen { align: center middle; }
    #dialog {
        width: 60;
        height: 11;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Add Variable")
            yield FieldRow("Name",    "var-name",    placeholder="e.g. height")
            yield FieldRow("Formula", "var-formula", placeholder="e.g. 2000 or sqrt(a^2+b^2)")
            with Horizontal():
                yield Button("Add",    id="btn-ok",     variant="primary")
                yield Button("Cancel", id="btn-cancel")

    @on(Button.Pressed, "#btn-ok")
    def confirm(self) -> None:
        name    = self.query_one("#var-name",    Input).value.strip()
        formula = self.query_one("#var-formula", Input).value.strip()
        self.dismiss((name, formula) if name and formula else None)

    @on(Button.Pressed, "#btn-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
