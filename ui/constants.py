"""
ui/constants.py

Shared constants and small pure helpers used across the UI layer.

Keeping them here — rather than in individual tab modules — means every tab
imports from one place and there is no risk of circular imports.
"""

from __future__ import annotations

from engine.optimization.greedy import NFDSolver, FFDSolver, BFDSolver, WFDSolver
from engine.optimization.branch_and_bound import BranchAndBoundSolver

# ---------------------------------------------------------------------------
# Solver registry
# Order matches the original CLI app: NFD, FFD, BFD, WFD, B&B
# ---------------------------------------------------------------------------

SOLVERS: dict[str, object] = {
    "NFD Greedy":             NFDSolver(),
    "FFD Greedy":             FFDSolver(),
    "BFD Greedy":             BFDSolver(),
    "WFD Greedy":             WFDSolver(),
    "Branch & Bound (Exact)": BranchAndBoundSolver(),
}

# (label, value) pairs for Textual Select widgets
ALGO_OPTIONS: list[tuple[str, str]] = [(name, name) for name in SOLVERS]

# Human-readable short tags and descriptions, keyed by solver.name
TAG: dict[str, str] = {
    "NFD Greedy":             "NFD",
    "FFD Greedy":             "FFD",
    "BFD Greedy":             "BFD",
    "WFD Greedy":             "WFD",
    "Branch & Bound (Exact)": "B&B",
}

DESC: dict[str, str] = {
    "NFD Greedy":             "Next Fit Decreasing",
    "FFD Greedy":             "First Fit Decreasing",
    "BFD Greedy":             "Best Fit Decreasing",
    "WFD Greedy":             "Worst Fit Decreasing",
    "Branch & Bound (Exact)": "Branch and Bound",
}

# Default price used when the project stock does not carry one.
# The Project tab exposes a price_per_bar input; this is the fallback.
DEFAULT_PRICE_PER_BAR: float = 0.0

# Perturbation used for the robustness / fragility score (mm).
PERTURBATION_MM: int = 5


# ---------------------------------------------------------------------------
# Step-size range helper  (mirrors original CLI app behaviour)
# ---------------------------------------------------------------------------

def step_range(start: float, stop: float, step_mm: float) -> tuple[float, ...]:
    """
    Generate evenly-spaced values from *start* to *stop* inclusive,
    advancing by *step_mm* each time.

    At least two values are always returned (start and stop), so a step
    larger than the span still gives [start, stop].

    Matches the original CLI app's sweep behaviour exactly.
    """
    if step_mm <= 0:
        raise ValueError(f"step_mm must be positive, got {step_mm}")
    vals: list[float] = []
    v = start
    while v <= stop + 1e-9:
        vals.append(round(v, 10))
        v += step_mm
    if len(vals) < 2:
        vals.append(round(stop, 10))
    return tuple(vals)
