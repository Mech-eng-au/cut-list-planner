"""
engine/optimization/branch_and_bound.py

Exact solver for the 1D cutting (bin-packing) problem via branch-and-bound.

Guarantees the minimum number of bars.
Uses FFD as a greedy upper bound for pruning; incorporates a
first-fit lower bound to prune branches that cannot improve.

Complexity: O(n!) worst case — intentionally limited to small instances
(n ≤ ~20) via MAX_PIECES guard. Use greedy solvers for large inputs.

Dependencies:
    engine.optimization.base
    engine.optimization.greedy   (for initial upper bound)
"""

from __future__ import annotations

import math
from copy import deepcopy

from .base import Bar, CutProblem, CutResult, Solver
from .greedy import FFDSolver

MAX_PIECES = 22   # hard guard; raise only with caution


class BranchAndBoundSolver(Solver):
    """
    Exact branch-and-bound solver.

    Algorithm sketch:
        1. Sort pieces descending.
        2. Use FFD to get an upper bound U on bar count.
        3. DFS: try assigning each unassigned piece to an existing bar
           or a new bar.
        4. Prune if current bar count ≥ best known U.
        5. Prune if first-fit lower bound on remaining pieces ≥ best known U.
        6. Record and update best solution whenever all pieces are placed.
    """

    @property
    def name(self) -> str:
        return "Branch & Bound (Exact)"

    @property
    def complexity(self) -> str:
        return "O(n!) worst case — practical for n ≤ 20"

    def solve(self, problem: CutProblem) -> CutResult:
        n = len(problem.pieces)
        if n > MAX_PIECES:
            raise ValueError(
                f"BranchAndBoundSolver is limited to {MAX_PIECES} pieces "
                f"(got {n}). Use a greedy solver for larger inputs."
            )

        pieces = sorted(problem.pieces, reverse=True)
        bl = problem.bar_length
        kerf = problem.kerf

        # --- upper bound via FFD ---
        ffd_result = FFDSolver().solve(problem)
        best: list[list[float]] = [list(b.pieces) for b in ffd_result.bars]
        best_count = [len(best)]

        def _lower_bound(remaining: list[float], current_bars: list[list[float]]) -> int:
            """
            Greedy lower bound: count minimum extra bars needed for *remaining*
            pieces ignoring items already partially filling current bars.
            """
            total_remaining = sum(remaining)
            min_extra = math.ceil(total_remaining / bl)
            return len(current_bars) + max(0, min_extra - len(current_bars))

        def _used(bar: list[float]) -> float:
            if not bar:
                return 0.0
            return sum(bar) + kerf * (len(bar) - 1)

        def _fits(bar: list[float], piece: float) -> bool:
            extra_kerf = kerf if bar else 0.0
            return _used(bar) + extra_kerf + piece <= bl + 1e-9

        def _branch(index: int, bars: list[list[float]]) -> None:
            if index == n:
                if len(bars) < best_count[0]:
                    best_count[0] = len(bars)
                    best.clear()
                    best.extend(deepcopy(bars))
                return

            remaining = pieces[index:]

            # lower-bound prune
            lb = _lower_bound(remaining, bars)
            if lb >= best_count[0]:
                return

            placed_in_existing = set()

            # Try placing into each distinct existing bar
            for i, bar in enumerate(bars):
                if _fits(bar, pieces[index]):
                    # Avoid symmetric branches: skip bars with same used()
                    sig = round(_used(bar), 6)
                    if sig in placed_in_existing:
                        continue
                    placed_in_existing.add(sig)
                    bar.append(pieces[index])
                    _branch(index + 1, bars)
                    bar.pop()

            # Try opening a new bar (only if worthwhile)
            if len(bars) + 1 < best_count[0]:
                bars.append([pieces[index]])
                _branch(index + 1, bars)
                bars.pop()

        _branch(0, [])

        result_bars = tuple(Bar(pieces=list(b)) for b in best)
        return CutResult(bars=result_bars, algorithm=self.name, problem=problem)
