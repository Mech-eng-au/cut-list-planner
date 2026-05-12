"""
ui/messages/sweep.py

Textual Message types posted by the sweep background worker.
"""

from __future__ import annotations

from textual.message import Message


class SweepProgressMessage(Message):
    """Posted periodically to update the progress bar."""

    def __init__(self, done: int, total: int, elapsed: float) -> None:
        super().__init__()
        self.done    = done
        self.total   = total
        self.elapsed = elapsed  # seconds


class SweepDoneMessage(Message):
    """Posted when the sweep finishes successfully."""

    def __init__(
        self,
        run,                                        # SweepRun
        axes_info: list[tuple[str, float, float, float]],  # (var, from, to, step)
        elapsed: float,                             # seconds
    ) -> None:
        super().__init__()
        self.run       = run
        self.axes_info = axes_info
        self.elapsed   = elapsed


class SweepErrorMessage(Message):
    """Posted when the sweep worker raises an unhandled exception."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message
