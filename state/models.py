"""
state/models.py

Core data model for a Cut-List Planner project.

Design invariants:
    - All models are plain dataclasses (no ORM, no DB, no UI coupling).
    - Validation is explicit and raises descriptive errors.
    - The project is the single root of state; nothing else is global.

Dependencies:
    engine.expressions   (for formula evaluation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.expressions import evaluate, Scope, ExpressionError


# ---------------------------------------------------------------------------
# Variable
# ---------------------------------------------------------------------------

@dataclass
class Variable:
    """
    A named scalar value (mm by default) that may be a literal or a formula.

    Attributes
    ----------
    name:    Symbolic identifier used in formulas.
    formula: Either a numeric string ('1200') or a formula ('2 * width + 10').
    value:   The resolved float value — set after evaluation.
    sweep:   Optional list of values for parametric sweep.
    """
    name: str
    formula: str
    value: float = 0.0
    sweep: list[float] = field(default_factory=list)

    def resolve(self, scope: Scope) -> float:
        """Evaluate formula in scope, update self.value, return result."""
        try:
            self.value = evaluate(self.formula, scope)
        except ExpressionError as exc:
            raise ValueError(f"Variable '{self.name}': {exc}") from exc
        return self.value


# ---------------------------------------------------------------------------
# Part definition
# ---------------------------------------------------------------------------

@dataclass
class Part:
    """
    A structural member to be cut.

    Attributes
    ----------
    label:        Human name, e.g. 'Top Rail'.
    length_expr:  Formula string that resolves to a length in mm.
    quantity:     How many of this part are needed.
    length_mm:    Resolved numeric length (set after evaluation).
    """
    label: str
    length_expr: str
    quantity: int = 1
    length_mm: float = 0.0

    def resolve(self, scope: Scope) -> float:
        try:
            self.length_mm = evaluate(self.length_expr, scope)
        except ExpressionError as exc:
            raise ValueError(f"Part '{self.label}': {exc}") from exc
        return self.length_mm


# ---------------------------------------------------------------------------
# Stock bar specification
# ---------------------------------------------------------------------------

@dataclass
class StockBar:
    """
    Physical stock bar specification.

    Attributes
    ----------
    length_mm:  Usable length of one raw bar (mm).
    width_mm:   Cross-section width, e.g. 90 for a 90×45 timber (mm).
    height_mm:  Cross-section height, e.g. 45 for a 90×45 timber (mm).
    kerf_mm:    Material consumed per saw cut (mm).
    """
    length_mm: float
    width_mm: float = 50.0
    height_mm: float = 50.0
    kerf_mm: float = 3.0

    def __post_init__(self):
        if self.length_mm <= 0:
            raise ValueError("Stock bar length must be positive")
        if self.width_mm <= 0:
            raise ValueError("Stock bar width must be positive")
        if self.height_mm <= 0:
            raise ValueError("Stock bar height must be positive")
        if self.kerf_mm < 0:
            raise ValueError("Kerf must be non-negative")

    @property
    def profile(self) -> str:
        """Human-readable cross-section, e.g. '90 x 45 mm'."""
        return f"{self.width_mm:g} x {self.height_mm:g} mm"


# ---------------------------------------------------------------------------
# Project (root of state)
# ---------------------------------------------------------------------------

@dataclass
class Project:
    """
    The root state object. One project = one cut-list scenario.

    Variables are resolved in declaration order (topological sort is a
    future improvement; for now, users must declare dependencies first).
    """
    name: str
    stock: StockBar
    variables: list[Variable] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)

    def resolve_all(self) -> Scope:
        """
        Evaluate all variables in order, then all part lengths.

        The scope is pre-seeded with stock constants so formulas can
        reference them directly without declaring variables:
            bar_width   = stock.width_mm
            bar_height  = stock.height_mm
            bar_length  = stock.length_mm
            kerf        = stock.kerf_mm

        Returns the final variable scope (variable_name -> value).
        Raises ValueError if any formula fails.
        """
        scope: Scope = {
            "bar_width":  self.stock.width_mm,
            "bar_height": self.stock.height_mm,
            "bar_length": self.stock.length_mm,
            "kerf":       self.stock.kerf_mm,
        }
        for var in self.variables:
            var.resolve(scope)
            scope[var.name] = var.value
        for part in self.parts:
            part.resolve(scope)
        return scope

    def expanded_pieces(self) -> list[float]:
        """
        Return the flat list of piece lengths, with quantity expansion.
        Requires resolve_all() to have been called.
        """
        return [part.length_mm for part in self.parts for _ in range(part.quantity)]
