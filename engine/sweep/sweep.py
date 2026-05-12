"""
engine/sweep/sweep.py

Parametric sweep engine for the Cut-List Planner.

A sweep iterates one or more variables across a range of values,
solves the cut problem at each point with one or more algorithms,
and collects all CutResult objects for downstream analysis.

Design invariants:
    - Sweep is a pure data-transformation pipeline.
    - No global state; every sweep is self-contained.
    - Results are always tagged with the parameter point that produced them.
    - Multi-variable sweeps produce the full Cartesian product of axes.
    - All solvers are run at every point (comparison is the point).

Key concepts:
    SweepAxis     — one variable varying across a numeric range
    SweepPoint    — one resolved snapshot of all axis values
    SweepResult   — one CutResult with the SweepPoint that created it
    SweepRun      — the full output of a completed sweep

Dependencies:
    engine.expressions
    engine.optimization.base
    state.models
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable, Sequence

from engine.expressions import evaluate, Scope, ExpressionError
from engine.optimization.base import CutProblem, CutResult, Solver
from state.models import Project


# ---------------------------------------------------------------------------
# Axis definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SweepAxis:
    """
    One variable to sweep.

    Attributes
    ----------
    variable_name:
        Must match a Variable.name in the Project.
    values:
        Ordered sequence of values to take. Use :func:`linear_range` or
        :func:`log_range` to build common patterns.
    """
    variable_name: str
    values: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.values)


def linear_range(start: float, stop: float, steps: int) -> tuple[float, ...]:
    """
    Evenly-spaced values from *start* to *stop* inclusive.

    Examples
    --------
    >>> linear_range(1000, 3000, 5)
    (1000.0, 1500.0, 2000.0, 2500.0, 3000.0)
    """
    if steps < 2:
        raise ValueError(f"steps must be ≥ 2, got {steps}")
    step = (stop - start) / (steps - 1)
    return tuple(round(start + i * step, 10) for i in range(steps))


def log_range(start: float, stop: float, steps: int) -> tuple[float, ...]:
    """
    Logarithmically-spaced values from *start* to *stop* inclusive.
    Both start and stop must be positive.
    """
    import math
    if start <= 0 or stop <= 0:
        raise ValueError("log_range requires positive start and stop")
    if steps < 2:
        raise ValueError(f"steps must be ≥ 2, got {steps}")
    log_start = math.log(start)
    log_stop = math.log(stop)
    return tuple(
        round(math.exp(log_start + i * (log_stop - log_start) / (steps - 1)), 10)
        for i in range(steps)
    )


def explicit_range(*values: float) -> tuple[float, ...]:
    """Explicit enumeration of values, e.g. for non-uniform grids."""
    return tuple(values)


# ---------------------------------------------------------------------------
# Sweep point (one resolved parameter snapshot)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SweepPoint:
    """
    One specific combination of swept variable values.

    Attributes
    ----------
    values:
        Mapping of variable_name → value at this point.
    index:
        Linear index in the full Cartesian product (for sorting/reference).
    """
    values: dict[str, float]
    index: int

    def label(self) -> str:
        """Human-readable parameter label, e.g. 'height=2000, width=1200'."""
        return ", ".join(f"{k}={v:g}" for k, v in self.values.items())


# ---------------------------------------------------------------------------
# Single sweep result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SweepResult:
    """
    One CutResult paired with the parameter point that produced it.

    Attributes
    ----------
    point:     The SweepPoint at which this result was computed.
    result:    The CutResult from the solver.
    solver:    Name of the algorithm used.
    """
    point: SweepPoint
    result: CutResult
    solver: str

    # Convenience pass-throughs
    @property
    def num_bars(self) -> int:
        return self.result.num_bars

    @property
    def total_waste(self) -> float:
        return self.result.total_waste

    @property
    def efficiency(self) -> float:
        return self.result.efficiency


# ---------------------------------------------------------------------------
# Full sweep run
# ---------------------------------------------------------------------------

@dataclass
class SweepRun:
    """
    Complete output of a parametric sweep.

    Attributes
    ----------
    axes:       The SweepAxis objects that defined this sweep.
    solvers:    The algorithm names included.
    results:    All SweepResult objects, in Cartesian-product order.
    errors:     Any (point, solver, message) triples that failed.
    """
    axes: list[SweepAxis]
    solvers: list[str]
    results: list[SweepResult] = field(default_factory=list)
    errors: list[tuple[SweepPoint, str, str]] = field(default_factory=list)

    @property
    def total_points(self) -> int:
        n = 1
        for ax in self.axes:
            n *= len(ax)
        return n

    @property
    def success_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def filter_by_solver(self, solver_name: str) -> list[SweepResult]:
        return [r for r in self.results if r.solver == solver_name]

    def filter_by_point(self, index: int) -> list[SweepResult]:
        return [r for r in self.results if r.point.index == index]

    def best_per_point(self) -> list[SweepResult]:
        """
        For each parameter point, return the single SweepResult with
        fewest bars (ties broken by lowest waste).
        """
        by_point: dict[int, list[SweepResult]] = {}
        for sr in self.results:
            by_point.setdefault(sr.point.index, []).append(sr)
        best = []
        for group in by_point.values():
            best.append(min(group, key=lambda r: (r.num_bars, r.total_waste)))
        return sorted(best, key=lambda r: r.point.index)


# ---------------------------------------------------------------------------
# Sweep executor
# ---------------------------------------------------------------------------

def run_sweep(
    project: Project,
    axes: list[SweepAxis],
    solvers: list[Solver],
    *,
    progress_callback: Callable[[int, int], None] | None = None,
) -> SweepRun:
    """
    Execute a full parametric sweep.

    For every combination of axis values × solvers:
        1. Override the swept variables in the project scope.
        2. Resolve all formulas (variables + parts).
        3. Build a CutProblem.
        4. Run each solver.
        5. Collect SweepResult.

    Parameters
    ----------
    project:
        The base project. Its variables are the non-swept defaults.
    axes:
        Which variables to sweep and over what values.
    solvers:
        Solver instances to run at every point.
    progress_callback:
        Optional callable(completed, total) for progress reporting.

    Returns
    -------
    SweepRun
        All results, errors, and metadata.
    """
    run = SweepRun(
        axes=axes,
        solvers=[s.name for s in solvers],
    )

    # Build Cartesian product of axis values
    axis_names = [ax.variable_name for ax in axes]
    axis_values = [ax.values for ax in axes]
    combinations = list(itertools.product(*axis_values))
    total = len(combinations) * len(solvers)
    completed = 0

    for idx, combo in enumerate(combinations):
        point = SweepPoint(
            values=dict(zip(axis_names, combo)),
            index=idx,
        )

        # Build override scope: start from project defaults, then apply sweep
        try:
            base_scope = _resolve_with_overrides(project, point.values)
        except Exception as exc:
            for solver in solvers:
                run.errors.append((point, solver.name, str(exc)))
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
            continue

        pieces = _expand_pieces(project, base_scope)
        if not pieces:
            for solver in solvers:
                run.errors.append((point, solver.name, "No pieces resolved"))
                completed += 1
            continue

        try:
            cut_problem = CutProblem(
                pieces=tuple(pieces),
                bar_length=project.stock.length_mm,
                kerf=project.stock.kerf_mm,
            )
        except ValueError as exc:
            for solver in solvers:
                run.errors.append((point, solver.name, str(exc)))
                completed += 1
            continue

        for solver in solvers:
            try:
                result = solver.solve(cut_problem)
                run.results.append(SweepResult(
                    point=point,
                    result=result,
                    solver=solver.name,
                ))
            except Exception as exc:
                run.errors.append((point, solver.name, str(exc)))
            finally:
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

    return run


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_with_overrides(project: Project, overrides: dict[str, float]) -> Scope:
    """
    Resolve project variables in order, injecting sweep overrides
    before any formula is evaluated that references them.
    The scope is pre-seeded with the same stock constants as
    Project.resolve_all() so that bar_width / bar_height / bar_length
    / kerf are always available in formulas.
    """
    scope: Scope = {
        "bar_width":  project.stock.width_mm,
        "bar_height": project.stock.height_mm,
        "bar_length": project.stock.length_mm,
        "kerf":       project.stock.kerf_mm,
    }
    for var in project.variables:
        if var.name in overrides:
            # Sweep override: use the given value directly, skip formula
            scope[var.name] = overrides[var.name]
        else:
            try:
                val = evaluate(var.formula, scope)
            except ExpressionError as exc:
                raise ValueError(f"Variable '{var.name}': {exc}") from exc
            scope[var.name] = val
    return scope


def _expand_pieces(project: Project, scope: Scope) -> list[float]:
    """Resolve all part lengths in scope and expand by quantity."""
    pieces = []
    for part in project.parts:
        try:
            length = evaluate(part.length_expr, scope)
        except ExpressionError as exc:
            raise ValueError(f"Part '{part.label}': {exc}") from exc
        pieces.extend([length] * part.quantity)
    return pieces
