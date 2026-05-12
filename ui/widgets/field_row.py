"""
A simple labelled-input row widget used throughout the Project tab
and modal screens.
"""

from __future__ import annotations

from textual.containers import Horizontal
from textual.widgets import Input, Label


class FieldRow(Horizontal):
    DEFAULT_CSS = """
    FieldRow {
        height: 3;
        margin-bottom: 0;
        align: left middle;
    }
    FieldRow Label {
        width: 18;
        padding: 0 1;
        color: $text;
        text-style: bold;
    }
    FieldRow Input {
        width: 1fr;
        background: $background;
        color: $text;
        border: solid $primary;
    }
    FieldRow Input:focus {
        border: solid $accent;
    }
    """

    def __init__(
        self,
        label: str,
        input_id: str,
        value: str = "",
        placeholder: str = "",
    ) -> None:
        super().__init__()
        self._label       = label
        self._input_id    = input_id
        self._value       = value
        self._placeholder = placeholder

    def compose(self):
        yield Label(self._label)
        yield Input(
            value=self._value,
            placeholder=self._placeholder,
            id=self._input_id,
        )
