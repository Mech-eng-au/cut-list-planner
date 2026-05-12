"""
ui/widgets/bar_diagram.py

BarDiagramWidget — a proportional block-character cut diagram.

Each stock bar is rendered as three lines:
    Line 0 – label: "Bar N  used=Xmm  waste=Ymm  eff=Z%"
    Line 1 – graphic: [████ piece ████][░ kerf ░][···waste···]
    Line 2 – blank spacer

The widget uses Textual's low-level render_line() / Strip / Segment API
so every character position is controlled precisely.

Clicking a DataTable row in the Results tab calls set_highlighted(row_index)
which scrolls to and highlights the matching bar.
"""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style
from textual.geometry import Size
from textual.reactive import reactive
from textual.strip import Strip
from textual.widget import Widget

from engine.optimization.base import Bar, CutResult

# Lines per bar in the diagram (label + graphic + spacer)
LINES_PER_BAR = 3
# Extra lines at the top (legend + blank separator)
HEADER_LINES  = 2


class BarDiagramWidget(Widget):
    """
    Proportional ASCII/block-character cut diagram for a CutResult.

    Diagram key:  █ = piece   ░ = kerf   · = waste
    """

    highlighted: reactive[int] = reactive(-1)

    _PIECE_CHAR = "█"
    _WASTE_CHAR = "·"
    _KERF_CHAR  = "░"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result: CutResult | None = None

    def set_result(self, result: CutResult | None) -> None:
        self._result = result
        self.highlighted = -1
        self.refresh()

    # ------------------------------------------------------------------
    # Textual height protocol
    # ------------------------------------------------------------------

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        n = len(self._result.bars) if self._result else 0
        return HEADER_LINES + n * LINES_PER_BAR

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        if width <= 0:
            return Strip.blank(width)

        if y == 0:
            return self._render_legend(width)
        if y == 1:
            return Strip.blank(width)

        body_y      = y - HEADER_LINES
        bar_index   = body_y // LINES_PER_BAR
        line_in_bar = body_y % LINES_PER_BAR

        if self._result is None or bar_index >= len(self._result.bars):
            return Strip.blank(width)

        bar          = self._result.bars[bar_index]
        is_highlight = (bar_index == self.highlighted)

        if line_in_bar == 0:
            return self._render_bar_label(bar_index, bar, width, is_highlight)
        elif line_in_bar == 1:
            return self._render_bar_graphic(bar_index, bar, width, is_highlight)
        else:
            return Strip.blank(width)

    # ------------------------------------------------------------------
    # Line renderers
    # ------------------------------------------------------------------

    def _render_legend(self, width: int) -> Strip:
        st_piece = Style.parse("bold cyan")
        st_kerf  = Style.parse("dim")
        st_waste = Style.parse("bold red")
        st_plain = Style.parse("")
        segs = [
            Segment("  Legend: ", st_plain),
            Segment("█ piece ", st_piece),
            Segment("  ░ kerf ", st_kerf),
            Segment("  · waste", st_waste),
        ]
        text    = "".join(s.text for s in segs)
        padding = max(0, width - len(text))
        segs.append(Segment(" " * padding, st_plain))
        return Strip(segs, width)

    def _render_bar_label(
        self, idx: int, bar: Bar, width: int, highlight: bool
    ) -> Strip:
        r     = self._result
        used  = bar.used(r.problem.kerf)
        waste = bar.waste(r.problem.bar_length, r.problem.kerf)
        eff   = used / r.problem.bar_length * 100 if r.problem.bar_length else 0
        marker = "▶" if highlight else " "
        label  = (
            f"{marker} Bar {idx + 1:>2}  "
            f"used={used:.0f} mm  "
            f"waste={waste:.0f} mm  "
            f"eff={eff:.0f}%"
        )
        label   = label[:width]
        padding = max(0, width - len(label))
        st      = Style.parse("bold green" if highlight else "bold")
        return Strip([Segment(label, st), Segment(" " * padding, st)], width)

    def _render_bar_graphic(
        self, idx: int, bar: Bar, width: int, highlight: bool
    ) -> Strip:
        r        = self._result
        bar_mm   = r.problem.bar_length
        kerf_mm  = r.problem.kerf
        st_piece = Style.parse("bold cyan")
        st_kerf  = Style.parse("dim white")
        st_waste = Style.parse("red")
        st_hl    = Style.parse("bold green")
        border   = Style.parse("bold green" if highlight else "dim")

        diagram_w = max(4, width - 2)

        # Build mm-level segment list: (length_mm, kind)
        mm_segs: list[tuple[float, str]] = []
        pieces_sorted = sorted(bar.pieces, reverse=True)
        for i, p in enumerate(pieces_sorted):
            mm_segs.append((p, "piece"))
            if i < len(pieces_sorted) - 1:
                mm_segs.append((kerf_mm, "kerf"))

        used_mm  = sum(s[0] for s in mm_segs)
        waste_mm = bar_mm - used_mm
        if waste_mm > 0:
            mm_segs.append((waste_mm, "waste"))

        total_mm = sum(s[0] for s in mm_segs)

        # Convert mm to character widths, keeping total == diagram_w
        char_segs: list[tuple[int, str]] = []
        allocated = 0
        for i, (mm, kind) in enumerate(mm_segs):
            if i == len(mm_segs) - 1:
                chars = diagram_w - allocated
            else:
                chars = max(1, round(mm / total_mm * diagram_w))
                chars = min(chars, diagram_w - allocated - (len(mm_segs) - i - 1))
            char_segs.append((max(1, chars), kind))
            allocated += max(1, chars)

        # Build Rich segments
        rich_segs: list[Segment] = [Segment("▕", border)]
        for chars, kind in char_segs:
            if kind == "piece":
                inner = self._PIECE_CHAR * chars
                rich_segs.append(Segment(inner, st_hl if highlight else st_piece))
            elif kind == "kerf":
                rich_segs.append(Segment(self._KERF_CHAR * chars, st_kerf))
            else:
                rich_segs.append(Segment(self._WASTE_CHAR * chars, st_waste))
        rich_segs.append(Segment("▏", border))

        return Strip(rich_segs, width)
