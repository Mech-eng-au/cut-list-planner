"""
engine/optimization/base.py

Abstract contract for all cutting-optimization algorithms.

Design invariants:
    - All solvers accept the same input signature.
    - All solvers produce the same CutResult output.
    - No solver imports UI or state modules.
    - Solvers are stateless; the same solver instance may be called many times.

Dependencies: none (only stdlib)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Input / output data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CutProblem:
    """
    Fully-specified cutting problem.

    Attributes
    ----------
    pieces:
        Lengths of pieces to cut (mm, positive reals).
    bar_length:
        Length of stock bar (mm, positive real).
    kerf:
        Width of the saw cut consumed per cut (mm, non-negative).
        Added to every piece except possibly the last on each bar.
    """
    pieces: tuple[float, ...]
    bar_length: float
    kerf: float = 0.0

    def __post_init__(self):
        if self.bar_length <= 0:
            raise ValueError(f"bar_length must be positive, got {self.bar_length}")
        if self.kerf < 0:
            raise ValueError(f"kerf must be non-negative, got {self.kerf}")
        for p in self.pieces:
            if p <= 0:
                raise ValueError(f"All piece lengths must be positive, got {p}")
            if p > self.bar_length:
                raise ValueError(
                    f"Piece length {p} exceeds bar_length {self.bar_length}"
                )


@dataclass
class Bar:
    """One stock bar and the pieces assigned to it."""
    pieces: list[float] = field(default_factory=list)

    def used(self, kerf: float = 0.0) -> float:
        """Total material consumed (piece lengths + kerfs between pieces)."""
        if not self.pieces:
            return 0.0
        return sum(self.pieces) + kerf * (len(self.pieces) - 1)

    def waste(self, bar_length: float, kerf: float = 0.0) -> float:
        return bar_length - self.used(kerf)

    def fits(self, piece: float, bar_length: float, kerf: float = 0.0) -> bool:
        """Would adding *piece* still fit within bar_length?"""
        extra_kerf = kerf if self.pieces else 0.0
        return self.used(kerf) + extra_kerf + piece <= bar_length


@dataclass(frozen=True)
class CutResult:
    """
    Result produced by any solver.

    Attributes
    ----------
    bars:
        Ordered list of Bar assignments.
    algorithm:
        Human-readable name of the algorithm that produced this result.
    problem:
        The original problem (for reference and verification).
    """
    bars: tuple[Bar, ...]
    algorithm: str
    problem: CutProblem

    # --- derived metrics ---

    @property
    def num_bars(self) -> int:
        return len(self.bars)

    @property
    def total_waste(self) -> float:
        return sum(b.waste(self.problem.bar_length, self.problem.kerf) for b in self.bars)

    @property
    def efficiency(self) -> float:
        """Material efficiency in [0, 1]."""
        total = self.num_bars * self.problem.bar_length
        return 1.0 - (self.total_waste / total) if total > 0 else 0.0

    def verify(self) -> bool:
        """
        Sanity-check: every piece in the problem appears exactly once across bars,
        and no bar is overfilled.
        """
        assigned = sorted(p for bar in self.bars for p in bar.pieces)
        expected = sorted(self.problem.pieces)
        if assigned != expected:
            return False
        for bar in self.bars:
            if bar.used(self.problem.kerf) > self.problem.bar_length + 1e-9:
                return False
        return True


# ---------------------------------------------------------------------------
# Abstract solver
# ---------------------------------------------------------------------------

class Solver(ABC):
    """
    Base class for all cut-list optimisation algorithms.

    Subclasses implement :meth:`solve` and declare their :attr:`name`
    and :attr:`complexity`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short human-readable algorithm name, e.g. 'FFD Greedy'."""

    @property
    @abstractmethod
    def complexity(self) -> str:
        """Big-O complexity string, e.g. 'O(n log n)'."""

    @abstractmethod
    def solve(self, problem: CutProblem) -> CutResult:
        """
        Find an assignment of pieces to bars.

        Parameters
        ----------
        problem:
            The fully-specified cut problem.

        Returns
        -------
        CutResult
            A valid (though not necessarily optimal) assignment.

        Raises
        ------
        ValueError
            If any piece exceeds the bar length.
        """
