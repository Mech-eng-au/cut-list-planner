"""
ui/widgets/axis_row.py

_AxisRow — one row in the Sweep tab's axis configuration panel.

Layout:
    [Var ▾──────────────] [From────] [To──────] [Step(mm)] [✕]
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Label, Select


class AxisRow(Horizontal):
    """
    One sweep-axis configuration row.

    Attributes
    ----------
    uid:
        Unique integer assigned at construction; used to build stable
        widget IDs so multiple rows can coexist without ID collisions.
    """

    DEFAULT_CSS = """
    AxisRow {
        height: 3;
        margin-bottom: 0;
        align: left middle;
    }
    AxisRow .axis-label {
        width: 5;
        padding: 0 1;
        color: $text-muted;
    }
    AxisRow Select {
        width: 2fr;
        margin-right: 1;
        min-width: 14;
    }
    AxisRow Input {
        width: 1fr;
        margin-right: 1;
        min-width: 8;
    }
    AxisRow Button {
        min-width: 3;
        width: 3;
    }
    """

    _counter: int = 0

    def __init__(
        self,
        var_options: list[tuple[str, str]],
        default_var: str | None = None,
    ) -> None:
        AxisRow._counter += 1
        self._uid         = AxisRow._counter
        self._var_options = var_options
        self._default_var = default_var or (var_options[0][1] if var_options else "")
        super().__init__()

    @property
    def uid(self) -> int:
        return self._uid

    def compose(self) -> ComposeResult:
        uid = self._uid
        yield Label("Var", classes="axis-label")
        yield Select(
            self._var_options,
            id=f"axis-var-{uid}",
            value=self._default_var,
            allow_blank=False,
        )
        yield Input(placeholder="From",     id=f"axis-from-{uid}")
        yield Input(placeholder="To",       id=f"axis-to-{uid}")
        yield Input(placeholder="Step(mm)", id=f"axis-step-{uid}")
        yield Button("✕", id=f"axis-del-{uid}", variant="error")

    def read(self) -> tuple[str, float, float, float] | None:
        """
        Return (var_name, from, to, step_mm) or None on any parse error.
        """
        uid      = self._uid
        var_name = self.query_one(f"#axis-var-{uid}", Select).value
        if var_name is Select.BLANK or not isinstance(var_name, str) or not var_name:
            return None
        try:
            frm  = float(self.query_one(f"#axis-from-{uid}", Input).value or 0)
            to   = float(self.query_one(f"#axis-to-{uid}",   Input).value or 0)
            step = float(self.query_one(f"#axis-step-{uid}", Input).value or 0)
        except ValueError:
            return None
        return var_name, frm, to, step

    def update_options(self, options: list[tuple[str, str]]) -> None:
        """Replace the variable dropdown options, preserving the current selection if valid."""
        sel: Select = self.query_one(f"#axis-var-{self._uid}", Select)
        current     = sel.value
        sel.set_options(options)
        valid = {v for _, v in options}
        if current in valid:
            sel.value = current
        elif options:
            sel.value = options[0][1]
