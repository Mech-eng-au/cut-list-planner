"""
ui/tabs/results_tab.py

Results tab — run solvers, show algorithm comparison, bar-by-bar cut plan,
visual diagram, workshop cut sequence, and robustness score.

Scrollability notes
-------------------
The entire tab is now a ScrollableContainer so all content is reachable
regardless of terminal height.  Inner panels use `height: auto` so they
expand to their content rather than clipping it.  The bar diagram scroll
region is kept but sized generously; the cut-sequence and robustness panels
are no longer fixed-height so the full text is always visible.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, DataTable, Label, Select, Static

from log import get_logger
from state.models import Project
from engine.optimization.base import CutProblem, CutResult
from engine.optimization.branch_and_bound import BranchAndBoundSolver

from ui.constants import SOLVERS, ALGO_OPTIONS, PERTURBATION_MM, TAG, DESC
from ui.widgets.bar_diagram import BarDiagramWidget, LINES_PER_BAR, HEADER_LINES
from ui.messages.results import ResultsDoneMessage, ResultsErrorMessage
from ui.formatters.comparison  import render_comparison_table
from ui.formatters.parts       import render_parts_table
from ui.formatters.cut_sequence import render_cut_plan_header, render_cut_sequence
from ui.formatters.robustness  import render_robustness

log = get_logger(__name__)


class ResultsTab(ScrollableContainer):
    """
    Results tab.  Inherits from ScrollableContainer so the user can scroll
    the entire tab when content exceeds the terminal height.
    """

    DEFAULT_CSS = """
    ResultsTab {
        padding: 1 2;
        /* ScrollableContainer handles overflow automatically */
    }
    #results-controls {
        height: 3;
        margin-bottom: 1;
    }
    #results-controls Button {
        margin-right: 1;
    }
    #results-running {
        height: 1;
        color: $accent;
        margin-bottom: 1;
    }
    #results-top-panels {
        height: auto;
        margin-bottom: 1;
    }
    #comparison-panel {
        width: 2fr;
        border: tall $panel;
        padding: 0 1;
        height: auto;
    }
    #parts-panel {
        width: 1fr;
        border: tall $panel;
        padding: 0 1;
        height: auto;
        margin-left: 1;
    }
    #cutplan-header-panel {
        border: tall $panel;
        padding: 0 1;
        height: auto;
        margin-bottom: 1;
    }
    #cutplan-heading {
        color: $accent;
        text-style: bold;
        height: 1;
        margin-top: 1;
    }
    #results-table {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
    }
    #diagram-heading {
        color: $accent;
        text-style: bold;
        height: 1;
    }
    #diagram-scroll {
        /* Enough rows to see most diagrams without scrolling internally;
           still scrollable for very long cut plans. */
        height: 20;
        border: tall $panel;
        margin-bottom: 1;
    }
    BarDiagramWidget {
        width: 1fr;
        height: auto;
    }
    #results-bottom-panels {
        height: auto;
        margin-bottom: 1;
    }
    /* ------------------------------------------------------------------ */
    /* Cut-sequence and robustness panels: auto height so nothing is clipped */
    /* ------------------------------------------------------------------ */
    #sequence-panel {
        width: 2fr;
        border: tall $panel;
        padding: 0 1;
        height: auto;
    }
    #robustness-panel {
        width: 1fr;
        border: tall $panel;
        padding: 0 1;
        height: auto;
        margin-left: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._worker = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="results-controls"):
            yield Button("▶  Run all algorithms", id="btn-run-all", variant="primary")
            yield Select(ALGO_OPTIONS, id="algo-select",
                         value="Branch & Bound (Exact)", allow_blank=False)
            yield Button("▶  Run selected", id="btn-run-one", variant="default")

        yield Static("", id="results-running")

        # Top panels: algorithm comparison | parts table
        with Horizontal(id="results-top-panels"):
            with Vertical(id="comparison-panel"):
                yield Static("Run algorithms to see comparison.", id="comparison-static")
            with Vertical(id="parts-panel"):
                yield Static("Load a project to see parts.", id="parts-static")

        # Cut plan summary header
        with Vertical(id="cutplan-header-panel"):
            yield Static("", id="cutplan-header-static")

        # Bar-by-bar cut plan table
        yield Label(
            "Bar-by-bar cut plan  (click a row to highlight in diagram)",
            id="cutplan-heading",
        )
        yield DataTable(id="results-table", show_cursor=True, cursor_type="row")

        # Visual diagram — kept in a fixed-height scroll so it doesn't
        # grow unboundedly when there are many bars.
        yield Label("Visual cut diagram", id="diagram-heading")
        with ScrollableContainer(id="diagram-scroll"):
            yield BarDiagramWidget(id="bar-diagram")

        # Bottom panels: workshop cut sequence | robustness
        # Both use Vertical (auto height) so full content is shown.
        with Horizontal(id="results-bottom-panels"):
            with Vertical(id="sequence-panel"):
                yield Static("", id="sequence-static")
            with Vertical(id="robustness-panel"):
                yield Static("", id="robustness-static")

    def on_mount(self) -> None:
        rt: DataTable = self.query_one("#results-table")
        rt.add_columns("Bar #", "Pieces (mm)", "Used (mm)", "Waste (mm)", "Eff.")

    def set_project(self, project: Project) -> None:
        self._project = project
        try:
            project.resolve_all()
        except Exception:
            pass
        self.query_one("#parts-static", Static).update(render_parts_table(project))

    def _status(self, msg: str) -> None:
        self.query_one("#results-running", Static).update(msg)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#btn-run-all")
    def handle_run_all(self) -> None:
        if self._worker and self._worker.is_running:
            self.app.notify("Already running.", severity="warning")
            return
        if self._project is None:
            self.app.notify("Load a project first.", severity="warning")
            return
        self._status("[cyan]Running all algorithms…[/cyan]")
        self._worker = self._run_worker(list(SOLVERS.values()), self._project)

    @on(Button.Pressed, "#btn-run-one")
    def handle_run_one(self) -> None:
        if self._worker and self._worker.is_running:
            self.app.notify("Already running.", severity="warning")
            return
        if self._project is None:
            self.app.notify("Load a project first.", severity="warning")
            return
        algo_name = self.query_one("#algo-select", Select).value
        solver    = SOLVERS[algo_name]
        self._status(f"[cyan]Running {algo_name}…[/cyan]")
        self._worker = self._run_worker([solver], self._project)

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    @work(thread=True)
    def _run_worker(self, solvers: list, project: Project) -> None:
        try:
            scope  = project.resolve_all()
            pieces = project.expanded_pieces()

            problem = CutProblem(
                pieces=tuple(pieces),
                bar_length=project.stock.length_mm,
                kerf=project.stock.kerf_mm,
            )

            all_results: list[dict] = []
            best_result: CutResult | None = None
            t_wall = time.perf_counter()

            for solver in solvers:
                t0     = time.perf_counter()
                result = solver.solve(problem)
                ms     = (time.perf_counter() - t0) * 1000
                sname  = solver.name

                all_results.append({
                    "tag":        TAG.get(sname, sname[:3].upper()),
                    "desc":       DESC.get(sname, sname),
                    "n_bars":     result.num_bars,
                    "waste_mm":   result.total_waste,
                    "efficiency": result.efficiency * 100,
                    "elapsed_ms": ms,
                    "result":     result,
                })

                if isinstance(solver, BranchAndBoundSolver):
                    best_result = result

            # If B&B wasn't in the run, pick the best heuristic result
            if best_result is None:
                best_result = min(
                    (r["result"] for r in all_results),
                    key=lambda r: (r.num_bars, r.total_waste),
                )

            # ----------------------------------------------------------
            # Robustness — use B&B for the exact tolerance search
            # ----------------------------------------------------------
            bar_length = project.stock.length_mm
            kerf       = project.stock.kerf_mm
            n_optimal  = best_result.num_bars
            bnb        = BranchAndBoundSolver()

            def _perturbed(overrun: int) -> list[float] | None:
                pp = [p + overrun for p in pieces]
                return None if any(p > bar_length for p in pp) else pp

            def _bars_for(pp: list[float]) -> int:
                prob = CutProblem(pieces=tuple(pp),
                                  bar_length=bar_length, kerf=kerf)
                return bnb.solve(prob).num_bars

            perturbed_5 = _perturbed(PERTURBATION_MM)
            if perturbed_5 is None:
                rob = {
                    "is_robust": False, "passes_check": False,
                    "n_bars_perturbed": None, "tolerance_mm": 0,
                }
            else:
                n_pert  = _bars_for(perturbed_5)
                passes  = n_pert <= n_optimal
                tolerance = 0
                for candidate in range(PERTURBATION_MM * 6 + 1):
                    pp = _perturbed(candidate)
                    if pp is None:
                        break
                    if _bars_for(pp) <= n_optimal:
                        tolerance = candidate
                    else:
                        break
                rob = {
                    "is_robust": passes, "passes_check": passes,
                    "n_bars_perturbed": n_pert, "tolerance_mm": tolerance,
                }

            elapsed_total = (time.perf_counter() - t_wall) * 1000
            log.info("Results worker done: %d solvers, best=%d bars, rob=%s, %.0f ms",
                     len(solvers), n_optimal, rob["is_robust"], elapsed_total)

            price = self.app.price_per_bar

            self.app.call_from_thread(
                self.on_results_done_message,
                ResultsDoneMessage(
                    all_results=all_results,
                    best_result=best_result,
                    rob=rob,
                    price_per_bar=price,
                    elapsed_total=elapsed_total,
                ),
            )

        except Exception as exc:
            log.exception("Results worker failed")
            self.app.call_from_thread(
                self.on_results_error_message,
                ResultsErrorMessage(str(exc)),
            )
        finally:
            self._status("Ready")
            self._worker = None

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_results_done_message(self, msg: ResultsDoneMessage) -> None:
        self._status(
            f"[green]Done[/green] — {len(msg.all_results)} algorithm(s) "
            f"in {msg.elapsed_total:.0f} ms"
        )

        result  = msg.best_result
        kerf    = result.problem.kerf
        bar_len = result.problem.bar_length

        # Build label map so the cut sequence can show part names
        label_map: dict[float, str] = {}
        if self._project:
            for part in self._project.parts:
                label_map[part.length_mm] = part.label

        # Algorithm tag for the cut plan header
        algo_tag = next(
            (r["tag"] + " — " + r["desc"]
             for r in msg.all_results
             if r["result"] is result),
            result.algorithm,
        )

        # Comparison panel
        self.query_one("#comparison-static", Static).update(
            render_comparison_table(msg.all_results, msg.price_per_bar)
        )

        # Parts panel
        if self._project:
            self.query_one("#parts-static", Static).update(
                render_parts_table(self._project)
            )

        # Cut plan header
        self.query_one("#cutplan-header-static", Static).update(
            render_cut_plan_header(
                bar_length=bar_len,
                kerf=kerf,
                num_bars=result.num_bars,
                waste_mm=result.total_waste,
                efficiency_pct=result.efficiency * 100,
                price_per_bar=msg.price_per_bar,
                algorithm_name=algo_tag,
            )
        )

        # Bar-by-bar table
        rt: DataTable = self.query_one("#results-table")
        rt.clear()
        for i, bar in enumerate(result.bars, 1):
            pieces_str = "  +  ".join(
                f"{p:.0f}" for p in sorted(bar.pieces, reverse=True)
            )
            used  = bar.used(kerf)
            waste = bar.waste(bar_len, kerf)
            eff   = used / bar_len * 100 if bar_len else 0
            rt.add_row(str(i), pieces_str, f"{used:.1f}", f"{waste:.1f}", f"{eff:.1f}%")

        # Visual diagram
        diagram: BarDiagramWidget = self.query_one("#bar-diagram")
        diagram.set_result(result)

        # Workshop cut sequence (with part labels)
        self.query_one("#sequence-static", Static).update(
            render_cut_sequence(result, label_map=label_map)
        )

        # Robustness score
        self.query_one("#robustness-static", Static).update(
            render_robustness(msg.rob, perturbation_mm=PERTURBATION_MM)
        )

        self.app.notify(
            f"Best: {result.num_bars} bars, waste {result.total_waste:.1f} mm, "
            f"efficiency {result.efficiency:.1%}",
            title="Results",
        )

    def on_results_error_message(self, msg: ResultsErrorMessage) -> None:
        self._status(f"[red]Error: {msg.message}[/red]")
        self.app.notify(msg.message, title="Error", severity="error")

    # ------------------------------------------------------------------
    # Row click → highlight diagram and scroll to it
    # ------------------------------------------------------------------

    @on(DataTable.RowHighlighted, "#results-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        diagram: BarDiagramWidget = self.query_one("#bar-diagram")
        diagram.highlighted = event.cursor_row

        # Scroll the inner diagram scroll region to the highlighted bar
        scroller: ScrollableContainer = self.query_one("#diagram-scroll")
        target_y = HEADER_LINES + event.cursor_row * LINES_PER_BAR
        scroller.scroll_to(y=target_y, animate=True)
