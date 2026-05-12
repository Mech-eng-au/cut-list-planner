"""
ui/formatters/comparison.py

Renders the algorithm comparison table as a Rich markup string.

No Textual imports — pure string → string transformation, fully testable
without a running TUI.
"""

from __future__ import annotations


def render_comparison_table(
    all_results: list[dict],
    price_per_bar: float,
) -> str:
    """
    Return a Rich-markup string for the algorithm comparison section.

    Each entry in *all_results* must have keys:
        tag, desc, n_bars, waste_mm, efficiency, elapsed_ms
    """
    if not all_results:
        return "[dim]No results yet.[/dim]"

    optimal_bars = min(r["n_bars"] for r in all_results)
    show_price   = price_per_bar > 0

    lines: list[str] = []
    lines.append("[bold cyan]ALGORITHM COMPARISON[/bold cyan]")
    lines.append("")

    hdr = f"  {'Algorithm':<28} {'Bars':>5}  {'Waste':>9}  {'Effic.':>7}  {'Time':>9}"
    if show_price:
        hdr += f"  {'Cost':>10}"
    lines.append(hdr)
    lines.append("  " + "─" * (len(hdr) - 2))

    bnb_ms: float | None = None

    for r in all_results:
        is_best   = r["n_bars"] == optimal_bars
        marker    = "[green]✓[/green]" if is_best else "[red]✗[/red]"
        ms        = r["elapsed_ms"]
        t_str     = f"{ms:.2f} ms" if ms < 1000 else f"{ms / 1000:.2f} s"
        cost_col  = f"  {r['n_bars'] * price_per_bar:>10.2f}" if show_price else ""
        waste_str = f"{r['waste_mm']:.1f} mm"
        eff_str   = f"{r['efficiency']:.1f}%"

        lines.append(
            f"{marker} {r['tag']:<6} {r['desc']:<20}  {r['n_bars']:>5}  "
            f"{waste_str:>9}  {eff_str:>7}  {t_str:>9}{cost_col}"
        )

        if r["tag"] == "B&B":
            bnb_ms = ms

    lines.append("")

    # Summary lines — which heuristics matched B&B?
    optimal_tags  = [r["tag"] for r in all_results if r["n_bars"] == optimal_bars]
    heuristics_ok = [t for t in optimal_tags if t != "B&B"]
    if heuristics_ok:
        lines.append(
            f"[green]✓ {' and '.join(heuristics_ok)} matched the B&B optimum "
            f"({optimal_bars} bar{'s' if optimal_bars != 1 else ''}).[/green]"
        )
    else:
        lines.append(
            f"[yellow]Only B&B found the true optimum ({optimal_bars} bar"
            f"{'s' if optimal_bars != 1 else ''}).[/yellow]"
        )

    # Which heuristics were suboptimal?
    suboptimal = [r for r in all_results if r["tag"] != "B&B" and r["n_bars"] > optimal_bars]
    if suboptimal:
        worst = max(suboptimal, key=lambda r: r["n_bars"])
        extra = worst["n_bars"] - optimal_bars
        lines.append(
            f"[red]✗ {worst['tag']} ({worst['desc']}) needed "
            f"{extra} extra bar{'s' if extra > 1 else ''}.[/red]"
        )

    if bnb_ms is not None:
        lines.append(
            f"[dim]⏱  B&B took {bnb_ms:.2f} ms to guarantee optimality.[/dim]"
        )

    return "\n".join(lines)
