"""
ui/formatters/cut_sequence.py

Renders two related sections as Rich markup strings:

    render_cut_plan_header  — summary block (bar length, kerf, bars needed,
                              optional price/cost, efficiency) that appears
                              above the bar-by-bar DataTable.

    render_cut_sequence     — the workshop step-by-step cutting instructions,
                              now including part labels on every step.

No Textual imports — pure string → string transformation.

Part-label support
------------------
CutResult.bars[].pieces is list[float] — the engine carries only lengths.
To show part labels in the cut sequence we accept an optional
``label_map: dict[float, str]`` that maps each unique length to a label.
The caller (results_tab) builds this from the Project before solving:

    label_map = {part.length_mm: part.label for part in project.parts}

When two parts share the same length the map will hold whichever label
was assigned last; that is acceptable because the instructions would be
identical for both.  Pass ``label_map=None`` (or omit it) to fall back
to showing lengths only.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Cut plan summary header
# ---------------------------------------------------------------------------

def render_cut_plan_header(
    bar_length: float,
    kerf: float,
    num_bars: int,
    waste_mm: float,
    efficiency_pct: float,
    price_per_bar: float = 0.0,
    algorithm_name: str = "",
) -> str:
    """Return a Rich-markup summary block for the cut plan."""
    lines: list[str] = []

    title = "DETAILED CUT PLAN"
    if algorithm_name:
        title += f"  —  {algorithm_name}"
    lines.append(f"[bold cyan]{title}[/bold cyan]")
    lines.append("")
    lines.append(f"  Bar length  : [bold]{bar_length:.0f} mm[/bold]")
    lines.append(f"  Cut loss    : {kerf:.1f} mm per cut")
    lines.append(f"  Bars needed : [bold]{num_bars}[/bold]")

    if price_per_bar > 0:
        total_price = num_bars * price_per_bar
        lines.append(f"  Price / bar : {price_per_bar:.2f}")
        lines.append(f"  Total price : [bold]{total_price:.2f}[/bold]")

    waste_pct = 100.0 - efficiency_pct
    lines.append(
        f"  Efficiency  : [bold]{efficiency_pct:.1f}%[/bold]  "
        f"(waste: {waste_mm:.1f} mm / {waste_pct:.1f}%)"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal: build step list for one bar
# ---------------------------------------------------------------------------

def _build_cut_steps(
    bar_pieces: list[float],
    bar_length: float,
    kerf: float,
) -> tuple[list[dict], float]:
    """
    Return (steps, waste_mm).

    Each step dict has:
        step, length, mark_at, offcut_before, offcut_after, is_last
    """
    ordered = sorted(bar_pieces, reverse=True)
    steps: list[dict] = []
    offcut = bar_length

    for i, length in enumerate(ordered):
        is_last      = (i == len(ordered) - 1)
        kerf_charged = 0.0 if is_last else kerf
        offcut_after = offcut - length - kerf_charged
        steps.append({
            "step":          i + 1,
            "length":        length,
            "mark_at":       length,
            "offcut_before": offcut,
            "offcut_after":  offcut_after,
            "is_last":       is_last,
        })
        offcut = offcut_after

    waste = bar_length - sum(ordered) - kerf * (len(ordered) - 1) if ordered else bar_length
    return steps, max(0.0, waste)


# ---------------------------------------------------------------------------
# Workshop cut sequence
# ---------------------------------------------------------------------------

def render_cut_sequence(
    result,                             # CutResult
    label_map: dict[float, str] | None = None,
) -> str:
    """
    Return a Rich-markup string for the full workshop cut sequence.

    Parameters
    ----------
    result:
        A CutResult from any solver.
    label_map:
        Optional mapping of piece length (mm) → part label string.
        When provided, every step shows the part name alongside its length.
        Build it with:  {part.length_mm: part.label for part in project.parts}
    """
    kerf    = result.problem.kerf
    bar_len = result.problem.bar_length

    lines: list[str] = []
    lines.append("[bold cyan]WORKSHOP CUT SEQUENCE[/bold cyan]")
    lines.append("[dim]Work left-to-right on each bar.[/dim]")
    lines.append("[dim]Mark each distance from the FREE (left) end of the current offcut.[/dim]")
    lines.append("[dim]Kerf is taken from the right side of each cut mark.[/dim]")
    lines.append("")

    total_bars = len(result.bars)

    for bar_idx, bar in enumerate(result.bars, 1):
        steps, waste = _build_cut_steps(list(bar.pieces), bar_len, kerf)
        n_cuts = len(steps)

        lines.append(
            f"[bold]Bar {bar_idx} of {total_bars}[/bold]"
            f"  ·  Full bar: {bar_len:.0f} mm"
            f"  ·  {n_cuts} cut{'s' if n_cuts != 1 else ''}"
        )
        lines.append("  " + "─" * 54)

        for s in steps:
            length    = s["length"]
            step_hdr  = f"  Step {s['step']} of {n_cuts}:"

            # Resolve label: use map if available, else show length only
            if label_map and length in label_map:
                piece_desc = f"{label_map[length]} ({length:.0f} mm)"
            else:
                piece_desc = f"{length:.0f} mm"

            if s["is_last"] and waste < 0.5:
                lines.append(
                    f"{step_hdr} No cut needed — offcut IS the final piece"
                )
                lines.append(
                    f"           [green]✓ Take:[/green] {piece_desc}"
                )
            elif s["is_last"]:
                lines.append(
                    f"{step_hdr} Mark [bold]{s['mark_at']:.0f} mm[/bold]"
                    f" from free end → CUT"
                )
                lines.append(
                    f"           [green]✓ Take:[/green] {piece_desc}"
                )
                lines.append(
                    f"           [red]✗ Discard waste:[/red] {waste:.1f} mm"
                )
            else:
                lines.append(
                    f"{step_hdr} Mark [bold]{s['mark_at']:.0f} mm[/bold]"
                    f" from free end → CUT"
                )
                lines.append(
                    f"           [green]✓ Set aside:[/green] {piece_desc}"
                )
                lines.append(
                    f"           → Remaining offcut: {s['offcut_after']:.0f} mm"
                )

            lines.append("")   # blank line between steps

        lines.append("")   # blank line between bars

    return "\n".join(lines)
