"""
ui/formatters/parts.py

Renders the part-lengths-and-quantities table as a Rich markup string.

No Textual imports.
"""

from __future__ import annotations

from state.models import Project


def render_parts_table(project: Project) -> str:
    """Return a Rich-markup string listing all resolved part lengths."""
    lines: list[str] = []
    lines.append("[bold cyan]PART LENGTHS & QUANTITIES[/bold cyan]")
    lines.append("")
    lines.append(f"  {'Label':<22} {'Qty':>4}  {'Length (mm)':>11}  Expression")
    lines.append("  " + "─" * 64)

    for part in project.parts:
        length_str = f"{part.length_mm:.1f}" if part.length_mm else "?"
        lines.append(
            f"  {part.label:<22} {part.quantity:>4}  {length_str:>11}  {part.length_expr}"
        )

    return "\n".join(lines)
