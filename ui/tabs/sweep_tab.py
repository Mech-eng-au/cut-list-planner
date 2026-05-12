"""
ui/tabs/sweep_tab.py

Sweep tab — configure parametric axes, run a sweep, display results.

Now inherits from ScrollableContainer so all content is reachable
regardless of terminal height.
"""

from __future__ import annotations

import time
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, DataTable, Label, Static

from log import get_logger
from state.models import Project
from engine.optimization.greedy import NFDSolver, FFDSolver, BFDSolver, WFDSolver
from engine.optimization.branch_and_bound import BranchAndBoundSolver
from engine.optimization.base import CutProblem
from engine.sweep import SweepAxis, run_sweep, algorithm_stats

from ui.constants import step_range, PERTURBATION_MM
from ui.widgets.axis_row import AxisRow
from ui.messages.sweep import SweepProgressMessage, SweepDoneMessage, SweepErrorMessage

log = get_logger(__name__)

_SWEEP_SOLVERS = [NFDSolver(), FFDSolver(), BFDSolver(), WFDSolver()]


class SweepTab(ScrollableContainer):
    """Sweep tab.  Scrollable so results table and summary are always reachable."""

    DEFAULT_CSS = """
    SweepTab {
        padding: 1 2;
    }
    .section-heading {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    #axes-container {
        height: auto;
        margin-bottom: 0;
        border: tall $panel;
        padding: 0 1;
    }
    #axes-header {
        height: 2;
        align: left middle;
        padding: 0 1;
        color: $text-muted;
    }
    #sweep-actions {
        height: 3;
        margin-top: 1;
        margin-bottom: 0;
    }
    #sweep-actions Button {
        margin-right: 1;
    }
    #sweep-progress {
        height: 1;
        color: $accent;
        margin-top: 1;
    }
    #sweep-eta {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
    }
    #sweep-errors {
        height: 1;
        color: $error;
    }
    #sweep-results-panel {
        height: auto;
        margin-bottom: 1;
    }
    #sweep-table {
        height: auto;
        min-height: 6;
        margin-bottom: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._var_options: list[tuple[str, str]] = []
        self._axis_rows: list[AxisRow] = []
        self._sweep_running = False

    def compose(self) -> ComposeResult:
        yield Label(
            "Sweep axes  (step = resolution in mm, e.g. 10 sweeps every 10 mm)",
            classes="section-heading",
        )

        with Vertical(id="axes-container"):
            yield Static(
                "  Variable                From       To         Step(mm)",
                id="axes-header",
            )

        with Horizontal(id="sweep-actions"):
            yield Button("+ Axis",       id="btn-add-axis",  variant="success")
            yield Button("− Axis",       id="btn-del-axis",  variant="default")
            yield Button("▶  Run sweep", id="btn-sweep-run", variant="primary")

        yield Static("", id="sweep-progress")
        yield Static("", id="sweep-eta")
        yield Static("", id="sweep-errors")

        yield Label("Results", classes="section-heading")
        yield Static("", id="sweep-results-panel")
        yield DataTable(id="sweep-table", show_cursor=True, cursor_type="row")

    def on_mount(self) -> None:
        st: DataTable = self.query_one("#sweep-table")
        st.add_columns("#", "Variable(s)", "Bars", "Waste (mm)", "Effic.", "±5mm")

    def set_project(self, project: Project) -> None:
        self._project = project
        self._var_options = [(v.name, v.name) for v in project.variables]

        container = self.query_one("#axes-container")
        for row in self._axis_rows:
            row.remove()
        self._axis_rows.clear()

        if self._var_options:
            self._add_axis_row()

    # ------------------------------------------------------------------
    # Axis management
    # ------------------------------------------------------------------

    def _add_axis_row(self) -> None:
        if not self._var_options:
            self.app.notify(
                "No variables to sweep — add variables in the Project tab.",
                severity="warning",
            )
            return
        used_vars = {r.read()[0] for r in self._axis_rows if r.read() is not None}
        default_var = next(
            (v for _, v in self._var_options if v not in used_vars),
            self._var_options[0][1],
        )
        row = AxisRow(list(self._var_options), default_var=default_var)
        self._axis_rows.append(row)
        self.query_one("#axes-container").mount(row)

    def _remove_last_axis_row(self) -> None:
        if not self._axis_rows:
            return
        row = self._axis_rows.pop()
        row.remove()

    @on(Button.Pressed, "#btn-add-axis")
    def handle_add_axis(self) -> None:
        self._add_axis_row()

    @on(Button.Pressed, "#btn-del-axis")
    def handle_del_axis(self) -> None:
        self._remove_last_axis_row()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("axis-del-"):
            try:
                uid = int(btn_id.split("-")[-1])
            except ValueError:
                return
            target = next((r for r in self._axis_rows if r.uid == uid), None)
            if target:
                self._axis_rows.remove(target)
                target.remove()
            event.stop()

    # ------------------------------------------------------------------
    # Run sweep
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#btn-sweep-run")
    def handle_sweep(self) -> None:
        if self._sweep_running:
            self.app.notify("A sweep is already running.", severity="warning")
            return
        if self._project is None:
            self.app.notify("Load a project first.", severity="warning")
            return
        if not self._axis_rows:
            self.app.notify("Add at least one sweep axis.", severity="warning")
            return

        axes_info: list[tuple[str, float, float, float]] = []
        seen_vars: set[str] = set()
        for row in self._axis_rows:
            parsed = row.read()
            if parsed is None:
                self.app.notify(
                    "Invalid sweep parameters — check From / To / Step.",
                    severity="warning",
                )
                return
            var_name, frm, to, step_mm = parsed
            if not isinstance(var_name, str) or not var_name:
                self.app.notify(
                    "Select a variable for every sweep axis.", severity="warning"
                )
                return
            if step_mm <= 0:
                self.app.notify(
                    f"Step must be > 0 mm (axis: {var_name}).", severity="warning"
                )
                return
            if frm >= to:
                self.app.notify(
                    f"From must be < To (axis: {var_name}).", severity="warning"
                )
                return
            if var_name in seen_vars:
                self.app.notify(
                    f"Variable '{var_name}' used in more than one axis.",
                    severity="warning",
                )
                return
            seen_vars.add(var_name)
            axes_info.append((var_name, frm, to, step_mm))

        total_combos = 1
        for _, frm, to, step_mm in axes_info:
            total_combos *= len(step_range(frm, to, step_mm))

        self.query_one("#sweep-progress", Static).update(
            f"Sweeping {len(axes_info)} dimension(s), "
            f"{total_combos:,} combinations …"
        )
        self.query_one("#sweep-eta",    Static).update("[……………………………………………………………………]   0.0%")
        self.query_one("#sweep-errors", Static).update("")
        self.query_one("#sweep-results-panel", Static).update("")

        st: DataTable = self.query_one("#sweep-table")
        st.clear()

        self._sweep_running = True
        log.info(
            "Sweep started: %d axis/axes, %d combinations — %s",
            len(axes_info),
            total_combos,
            ", ".join(f"{v}:[{f:g}→{t:g} step {s:g}]" for v, f, t, s in axes_info),
        )
        self._run_sweep_worker(axes_info, total_combos)

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    @work(thread=True)
    def _run_sweep_worker(
        self,
        axes_info: list[tuple[str, float, float, float]],
        total_combos: int,
    ) -> None:
        try:
            axes = [
                SweepAxis(var_name, step_range(frm, to, step_mm))
                for var_name, frm, to, step_mm in axes_info
            ]

            t_start = time.perf_counter()

            def progress_cb(done: int, total: int) -> None:
                elapsed = time.perf_counter() - t_start
                log.debug("Sweep progress: %d/%d (%.1fs elapsed)", done, total, elapsed)
                self.post_message(SweepProgressMessage(done, total, elapsed))

            run = run_sweep(
                self._project,
                axes,
                _SWEEP_SOLVERS,
                progress_callback=progress_cb,
            )

            elapsed = time.perf_counter() - t_start
            log.info(
                "Sweep finished: %d results, %d errors, %.1fs",
                run.success_count,
                run.error_count,
                elapsed,
            )
            if run.error_count:
                log.warning("First sweep error: %s", run.errors[0][2])

            self.post_message(SweepDoneMessage(run, axes_info, elapsed))

        except Exception as exc:
            log.exception("Sweep worker crashed")
            self.post_message(SweepErrorMessage(str(exc)))

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_sweep_progress_message(self, msg: SweepProgressMessage) -> None:
        done, total, elapsed = msg.done, msg.total, msg.elapsed
        if total == 0:
            return
        pct = done / total * 100
        eta = (elapsed / done * (total - done)) if done else 0

        bar_w  = 36
        filled = int(bar_w * done / total)
        bar_s  = "█" * filled + "·" * (bar_w - filled)

        self.query_one("#sweep-progress", Static).update(
            f"[{bar_s}] {pct:5.1f}%"
        )
        if eta > 0:
            self.query_one("#sweep-eta", Static).update(
                f"  elapsed {elapsed:5.1f}s  ETA {eta:5.1f}s"
            )

    def on_sweep_done_message(self, msg: SweepDoneMessage) -> None:
        self._sweep_running = False
        run       = msg.run
        axes_info = msg.axes_info
        elapsed   = msg.elapsed

        bar_s = "█" * 36
        self.query_one("#sweep-progress", Static).update(
            f"[{bar_s}] 100.0%  done in {elapsed:.1f}s"
        )
        self.query_one("#sweep-eta", Static).update("")

        if run.error_count:
            self.query_one("#sweep-errors", Static).update(
                f"⚠  {run.error_count} error(s) — first: {run.errors[0][2]}"
            )

        if not run.results:
            self.query_one("#sweep-results-panel", Static).update(
                "[red]No valid combinations found in sweep range.[/red]"
            )
            return

        best_per_point = run.best_per_point()
        best_per_point_sorted = sorted(
            best_per_point, key=lambda r: (r.num_bars, r.total_waste)
        )

        bnb = BranchAndBoundSolver()

        def _robust(point_vals: dict[str, float]) -> bool:
            from engine.sweep.sweep import _resolve_with_overrides, _expand_pieces
            try:
                scope   = _resolve_with_overrides(self._project, point_vals)
                pieces  = _expand_pieces(self._project, scope)
                perturbed = [p + PERTURBATION_MM for p in pieces]
                if any(p > self._project.stock.length_mm for p in perturbed):
                    return False
                prob_orig = CutProblem(
                    pieces=tuple(pieces),
                    bar_length=self._project.stock.length_mm,
                    kerf=self._project.stock.kerf_mm,
                )
                prob_pert = CutProblem(
                    pieces=tuple(perturbed),
                    bar_length=self._project.stock.length_mm,
                    kerf=self._project.stock.kerf_mm,
                )
                n_orig = bnb.solve(prob_orig).num_bars
                n_pert = bnb.solve(prob_pert).num_bars
                return n_pert <= n_orig
            except Exception:
                return False

        top_n = 10
        top   = best_per_point_sorted[:top_n]
        for r in top:
            r.__dict__["_robust"] = _robust(r.point.values)

        stats     = algorithm_stats(run)
        stats_str = "  |  ".join(
            f"{s.name.split()[0]}: {s.win_count} wins ({s.win_rate:.0%})"
            for s in stats
        )

        best_waste = best_per_point_sorted[0].total_waste
        best_bars  = best_per_point_sorted[0].num_bars
        ties = sum(
            1 for r in best_per_point_sorted
            if r.num_bars == best_bars and abs(r.total_waste - best_waste) < 0.1
        )
        total_valid = len(best_per_point_sorted)

        summary_lines = [
            f"[bold cyan]DIMENSION SWEEP — Top {min(top_n, total_valid)} Results"
            f"  (out of {total_valid:,} valid combinations)[/bold cyan]",
            "",
            f"Algorithm comparison:  {stats_str}",
            "",
            f"[dim]±{PERTURBATION_MM}mm column: ✓ plan still fits in the same number of bars if[/dim]",
            f"[dim]             every piece is cut {PERTURBATION_MM} mm long.[/dim]",
            f"[dim]             ✗ would need an extra bar — leave more margin![/dim]",
        ]
        if ties > 1:
            summary_lines.append(
                f"\n[yellow]ℹ  {ties} combinations tied for the best result.[/yellow]"
            )

        self.query_one("#sweep-results-panel", Static).update(
            "\n".join(summary_lines)
        )

        swept_vars = [var_name for var_name, *_ in axes_info]
        var_col_header = " / ".join(v.capitalize() for v in swept_vars)

        st: DataTable = self.query_one("#sweep-table")
        st.clear(columns=True)
        st.add_columns("#", var_col_header, "Bars", "Waste (mm)", "Effic.", "±5mm")

        for rank, r in enumerate(top, 1):
            var_col = "  ".join(
                f"{k}={r.point.values.get(k, '?'):g}" for k in swept_vars
            )
            rob_tag  = "✓" if r.__dict__.get("_robust") else "✗"
            st.add_row(
                str(rank),
                var_col,
                str(r.num_bars),
                f"{r.total_waste:.1f}",
                f"{r.efficiency:.1%}",
                rob_tag,
            )

        self.app.notify(
            f"Sweep complete: {total_valid:,} valid points in {elapsed:.1f}s",
            title="Sweep done",
        )

    def on_sweep_error_message(self, msg: SweepErrorMessage) -> None:
        self._sweep_running = False
        log.error("Sweep error: %s", msg.message)
        self.query_one("#sweep-errors", Static).update(
            f"[red]Sweep error: {msg.message}[/red]"
        )
        self.app.notify(msg.message, title="Sweep error", severity="error")
