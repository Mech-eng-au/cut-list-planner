"""
ui/messages/results.py

Textual Message types posted by the results background worker.
"""

from __future__ import annotations

from textual.message import Message

from engine.optimization.base import CutResult


class ResultsDoneMessage(Message):
    """Posted when all solvers have finished and robustness is computed."""

    def __init__(
        self,
        all_results: list[dict],
        best_result: CutResult,
        rob: dict,
        price_per_bar: float,
        elapsed_total: float,
    ) -> None:
        super().__init__()
        self.all_results   = all_results    # one dict per solver run
        self.best_result   = best_result    # B&B result, or best heuristic
        self.rob           = rob            # robustness dict
        self.price_per_bar = price_per_bar  # may be 0.0
        self.elapsed_total = elapsed_total  # wall-clock ms


class ResultsErrorMessage(Message):
    """Posted when the results worker raises an unhandled exception."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message
