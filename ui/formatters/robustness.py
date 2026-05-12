"""
ui/formatters/robustness.py

Renders the robustness / fragility score section as a Rich markup string.

No Textual imports.
"""

from __future__ import annotations


def render_robustness(
    rob: dict,
    perturbation_mm: int = 5,
) -> str:
    """
    Return a Rich-markup string for the robustness / fragility section.

    *rob* must have keys:
        is_robust          bool
        n_bars_perturbed   int | None
        tolerance_mm       int
    """
    lines: list[str] = []
    lines.append("[bold cyan]ROBUSTNESS / FRAGILITY SCORE[/bold cyan]")
    lines.append("")
    lines.append(
        f"[dim]Question: if every piece is cut {perturbation_mm} mm too long,[/dim]"
    )
    lines.append("[dim]does the plan still fit in the same number of bars?[/dim]")
    lines.append("")

    if rob["n_bars_perturbed"] is None:
        lines.append(
            "[red]✗ FRAGILE — perturbed pieces exceed bar length entirely.[/red]"
        )
        lines.append("  Tolerance: 0 mm")

    elif rob["is_robust"]:
        lines.append("[green]✓ ROBUST[/green]")
        lines.append(
            f"  All pieces +{perturbation_mm} mm → still fits in "
            f"{rob['n_bars_perturbed']} bar(s).  No problem."
        )
        lines.append(
            f"  Exact tolerance: up to [bold]{rob['tolerance_mm']} mm[/bold] per piece "
            f"before an extra bar is needed."
        )

    else:
        lines.append("[red]✗ FRAGILE[/red]")
        lines.append(
            f"  All pieces +{perturbation_mm} mm → requires "
            f"{rob['n_bars_perturbed']} bar(s) — one extra!"
        )
        lines.append(f"  Exact tolerance: only {rob['tolerance_mm']} mm per piece.")
        lines.append(
            "  [yellow]Recommendation:[/yellow] add a safety margin to piece lengths,\n"
            "  or choose a dimension with ✓ in the sweep ±5mm column."
        )

    return "\n".join(lines)
