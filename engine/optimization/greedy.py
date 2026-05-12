"""
engine/optimization/greedy.py

Greedy bin-packing heuristics for the 1D cutting problem.

Implemented algorithms:
    NFD — Next Fit Decreasing    O(n log n)  (naive; demonstrates suboptimal)
    FFD — First Fit Decreasing   O(n log n)  (classic greedy; industry standard)
    BFD — Best Fit Decreasing    O(n log n)  (minimises waste per bar)
    WFD — Worst Fit Decreasing   O(n log n)  (maximises remaining space)

All algorithms share the same interface (Solver base class).
None modifies its input.

Dependencies:
    engine.optimization.base
"""

from __future__ import annotations

from .base import Bar, CutProblem, CutResult, Solver


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _descending(pieces: tuple[float, ...]) -> list[float]:
    return sorted(pieces, reverse=True)


def _make_result(bars: list[Bar], algorithm: str, problem: CutProblem) -> CutResult:
    return CutResult(bars=tuple(bars), algorithm=algorithm, problem=problem)


# ---------------------------------------------------------------------------
# NFD — Next Fit Decreasing
# ---------------------------------------------------------------------------

class NFDSolver(Solver):
    """
    Next Fit Decreasing.

    For each piece (sorted largest-first), try only the *current* (last-opened)
    bar. If the piece does not fit, close that bar forever and open a new one.

    This is the simplest possible heuristic — O(n log n) sort + O(n) placement —
    but it often uses more bars than necessary because it never revisits earlier
    bars. Its main purpose is to show a suboptimal baseline in comparisons.
    """

    @property
    def name(self) -> str:
        return "NFD Greedy"

    @property
    def complexity(self) -> str:
        return "O(n log n)"

    def solve(self, problem: CutProblem) -> CutResult:
        bars: list[Bar] = []
        for piece in _descending(problem.pieces):
            if bars and bars[-1].fits(piece, problem.bar_length, problem.kerf):
                bars[-1].pieces.append(piece)
            else:
                bar = Bar()
                bar.pieces.append(piece)
                bars.append(bar)
        return _make_result(bars, self.name, problem)


# ---------------------------------------------------------------------------
# FFD — First Fit Decreasing
# ---------------------------------------------------------------------------

class FFDSolver(Solver):
    """
    First Fit Decreasing.

    For each piece (sorted largest-first), place it in the first bar
    that has enough remaining capacity. If none, open a new bar.

    Complexity: O(n log n) sort + O(n·b) placement where b = num bars.
    In practice very fast; b is small.
    """

    @property
    def name(self) -> str:
        return "FFD Greedy"

    @property
    def complexity(self) -> str:
        return "O(n log n)"

    def solve(self, problem: CutProblem) -> CutResult:
        bars: list[Bar] = []
        for piece in _descending(problem.pieces):
            placed = False
            for bar in bars:
                if bar.fits(piece, problem.bar_length, problem.kerf):
                    bar.pieces.append(piece)
                    placed = True
                    break
            if not placed:
                bar = Bar()
                bar.pieces.append(piece)
                bars.append(bar)
        return _make_result(bars, self.name, problem)


# ---------------------------------------------------------------------------
# BFD — Best Fit Decreasing
# ---------------------------------------------------------------------------

class BFDSolver(Solver):
    """
    Best Fit Decreasing.

    For each piece (sorted largest-first), place it in the bar that has
    the *least* remaining space while still fitting. This minimises waste
    fragmentation.

    Complexity: O(n log n) sort + O(n·b) placement.
    """

    @property
    def name(self) -> str:
        return "BFD Greedy"

    @property
    def complexity(self) -> str:
        return "O(n log n)"

    def solve(self, problem: CutProblem) -> CutResult:
        bars: list[Bar] = []
        for piece in _descending(problem.pieces):
            best_bar: Bar | None = None
            best_remaining = float("inf")
            for bar in bars:
                remaining = bar.waste(problem.bar_length, problem.kerf)
                extra_kerf = problem.kerf if bar.pieces else 0.0
                space_after = remaining - extra_kerf - piece
                if space_after >= -1e-9 and space_after < best_remaining:
                    best_bar = bar
                    best_remaining = space_after
            if best_bar is not None:
                best_bar.pieces.append(piece)
            else:
                bar = Bar()
                bar.pieces.append(piece)
                bars.append(bar)
        return _make_result(bars, self.name, problem)


# ---------------------------------------------------------------------------
# WFD — Worst Fit Decreasing
# ---------------------------------------------------------------------------

class WFDSolver(Solver):
    """
    Worst Fit Decreasing.

    For each piece (sorted largest-first), place it in the bar with the
    *most* remaining space. Tends to spread load evenly across bars,
    sometimes reducing the maximum bar count on irregular inputs.

    Complexity: O(n log n) sort + O(n·b) placement.
    """

    @property
    def name(self) -> str:
        return "WFD Greedy"

    @property
    def complexity(self) -> str:
        return "O(n log n)"

    def solve(self, problem: CutProblem) -> CutResult:
        bars: list[Bar] = []
        for piece in _descending(problem.pieces):
            worst_bar: Bar | None = None
            worst_remaining = -1.0
            for bar in bars:
                remaining = bar.waste(problem.bar_length, problem.kerf)
                extra_kerf = problem.kerf if bar.pieces else 0.0
                space_after = remaining - extra_kerf - piece
                if space_after >= -1e-9 and space_after > worst_remaining:
                    worst_bar = bar
                    worst_remaining = space_after
            if worst_bar is not None:
                worst_bar.pieces.append(piece)
            else:
                bar = Bar()
                bar.pieces.append(piece)
                bars.append(bar)
        return _make_result(bars, self.name, problem)


# ---------------------------------------------------------------------------
# Convenience registry
# ---------------------------------------------------------------------------

GREEDY_SOLVERS: dict[str, Solver] = {
    "nfd": NFDSolver(),
    "ffd": FFDSolver(),
    "bfd": BFDSolver(),
    "wfd": WFDSolver(),
}
