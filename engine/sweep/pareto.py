"""
engine/sweep/pareto.py

Pareto-front analysis over SweepRun results.

Supports multi-objective analysis where objectives are any combination of:
    - num_bars      (minimise)
    - total_waste   (minimise)
    - efficiency    (maximise — converted to minimise internally)

Also supports identifying which algorithm wins most often across sweep points,
and computing sensitivity: how much does the objective change per unit of a
swept variable?

Dependencies:
    engine.sweep.sweep
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .sweep import SweepResult, SweepRun


# ---------------------------------------------------------------------------
# Objective accessors
# ---------------------------------------------------------------------------

OBJECTIVES: dict[str, tuple[Callable[[SweepResult], float], str]] = {
    "num_bars":    (lambda r: float(r.num_bars),   "minimise"),
    "total_waste": (lambda r: r.total_waste,        "minimise"),
    "efficiency":  (lambda r: -r.efficiency,        "minimise (negated)"),
}


# ---------------------------------------------------------------------------
# Pareto front
# ---------------------------------------------------------------------------

def pareto_front(
    results: list[SweepResult],
    objectives: list[str] | None = None,
) -> list[SweepResult]:
    """
    Return the Pareto-optimal subset of *results*.

    A result r1 dominates r2 if r1 is at least as good on all objectives
    and strictly better on at least one.

    Parameters
    ----------
    results:
        Any list of SweepResult (may span multiple points and algorithms).
    objectives:
        Subset of {'num_bars', 'total_waste', 'efficiency'}.
        Defaults to ['num_bars', 'total_waste'].

    Returns
    -------
    list[SweepResult]
        Non-dominated results in input order.
    """
    if objectives is None:
        objectives = ["num_bars", "total_waste"]

    accessors = [OBJECTIVES[o][0] for o in objectives]

    def dominates(a: SweepResult, b: SweepResult) -> bool:
        a_vals = [f(a) for f in accessors]
        b_vals = [f(b) for f in accessors]
        return (
            all(av <= bv for av, bv in zip(a_vals, b_vals))
            and any(av < bv for av, bv in zip(a_vals, b_vals))
        )

    dominated: set[int] = set()
    for i in range(len(results)):
        for j in range(len(results)):
            if i == j or j in dominated:
                continue
            if dominates(results[i], results[j]):
                dominated.add(j)

    return [r for i, r in enumerate(results) if i not in dominated]


# ---------------------------------------------------------------------------
# Algorithm win-rate analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AlgorithmStats:
    """Aggregated performance of one algorithm across a sweep."""
    name: str
    win_count: int          # number of points where this was best
    total_points: int       # total points it was evaluated at
    avg_bars: float
    avg_waste: float
    avg_efficiency: float

    @property
    def win_rate(self) -> float:
        return self.win_count / self.total_points if self.total_points else 0.0


def algorithm_stats(run: SweepRun) -> list[AlgorithmStats]:
    """
    Compute per-algorithm statistics across all sweep points.

    'Best' at a point means fewest bars, ties broken by lowest waste.
    """
    # Group by solver name
    by_solver: dict[str, list[SweepResult]] = {}
    for sr in run.results:
        by_solver.setdefault(sr.solver, []).append(sr)

    # Determine winner at each point
    best_per_point = run.best_per_point()
    win_counts: dict[str, int] = {name: 0 for name in by_solver}
    for best in best_per_point:
        win_counts[best.solver] = win_counts.get(best.solver, 0) + 1

    stats = []
    for name, results in by_solver.items():
        n = len(results)
        stats.append(AlgorithmStats(
            name=name,
            win_count=win_counts.get(name, 0),
            total_points=n,
            avg_bars=sum(r.num_bars for r in results) / n,
            avg_waste=sum(r.total_waste for r in results) / n,
            avg_efficiency=sum(r.efficiency for r in results) / n,
        ))

    return sorted(stats, key=lambda s: (-s.win_rate, s.avg_bars))


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SensitivityPoint:
    variable_name: str
    variable_value: float
    solver: str
    num_bars: int
    total_waste: float
    efficiency: float


def sensitivity(
    run: SweepRun,
    variable_name: str,
    solver_name: str | None = None,
) -> list[SensitivityPoint]:
    """
    Extract a 1-D sensitivity series: objective values as one variable changes.

    Only meaningful for single-axis sweeps or when all other axes are constant.
    If solver_name is None, returns results for all solvers (interleaved).

    Results are sorted by variable value.
    """
    points = []
    for sr in run.results:
        if variable_name not in sr.point.values:
            continue
        if solver_name and sr.solver != solver_name:
            continue
        points.append(SensitivityPoint(
            variable_name=variable_name,
            variable_value=sr.point.values[variable_name],
            solver=sr.solver,
            num_bars=sr.num_bars,
            total_waste=sr.total_waste,
            efficiency=sr.efficiency,
        ))
    return sorted(points, key=lambda p: (p.solver, p.variable_value))
