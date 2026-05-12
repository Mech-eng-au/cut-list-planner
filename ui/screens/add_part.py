"""
Modal screen for adding a new Part to the project.
Dismissed with (label, expr, qty) on confirm, or None on cancel.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from ui.widgets.field_row import FieldRow


class AddPartScreen(ModalScreen[tuple[str, str, int] | None]):
    DEFAULT_CSS = """
    AddPartScreen { align: center middle; }
    #dialog {
        width: 60;
        height: 13;
        border: thick $accent;
        background: $secondary;
        padding: 1 2;
    }
    #dialog Label {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }
    #dialog Button {
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

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Add Part")
            yield FieldRow("Label",      "part-label", placeholder="e.g. Vertical")
            yield FieldRow("Expression", "part-expr",  placeholder="e.g. height - bar_width")
            yield FieldRow("Quantity",   "part-qty",   placeholder="1")
            with Horizontal():
                yield Button("Add",    id="btn-ok",     variant="primary")
                yield Button("Cancel", id="btn-cancel")

    @on(Button.Pressed, "#btn-ok")
    def confirm(self) -> None:
        label = self.query_one("#part-label", Input).value.strip()
        expr  = self.query_one("#part-expr",  Input).value.strip()
        try:
            qty = int(self.query_one("#part-qty", Input).value.strip() or "1")
        except ValueError:
            qty = 1
        self.dismiss((label, expr, qty) if label and expr else None)

    @on(Button.Pressed, "#btn-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
