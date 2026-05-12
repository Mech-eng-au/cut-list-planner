"""
engine/optimization/metrics.py

Comparative metrics for CutResult objects.
Supports algorithm benchmarking and Pareto analysis.

Dependencies:
    engine.optimization.base
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import CutResult


@dataclass(frozen=True)
class ResultMetrics:
    algorithm: str
    num_bars: int
    total_waste_mm: float
    efficiency_pct: float   # 0–100
    is_verified: bool


def measure(result: CutResult) -> ResultMetrics:
    return ResultMetrics(
        algorithm=result.algorithm,
        num_bars=result.num_bars,
        total_waste_mm=round(result.total_waste, 3),
        efficiency_pct=round(result.efficiency * 100, 2),
        is_verified=result.verify(),
    )


def compare(results: list[CutResult]) -> list[ResultMetrics]:
    """Return metrics for all results, sorted by num_bars then waste."""
    metrics = [measure(r) for r in results]
    return sorted(metrics, key=lambda m: (m.num_bars, m.total_waste_mm))


def pareto_front(results: list[CutResult]) -> list[CutResult]:
    """
    Return the Pareto-optimal subset of results on the
    (num_bars, total_waste) objective space (minimise both).
    """
    dominated: set[int] = set()
    for i, r1 in enumerate(results):
        for j, r2 in enumerate(results):
            if i == j or j in dominated:
                continue
            # r2 dominates r1 if it is ≤ on all objectives and < on at least one
            if (r2.num_bars <= r1.num_bars and r2.total_waste <= r1.total_waste and
                    (r2.num_bars < r1.num_bars or r2.total_waste < r1.total_waste)):
                dominated.add(i)
                break
    return [r for i, r in enumerate(results) if i not in dominated]
