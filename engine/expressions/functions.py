"""
engine/expressions/functions.py

Whitelist of allowed mathematical functions for the expression evaluator.

Design invariants:
  - This module is the ONLY place where allowed functions are defined.
  - No function here has side effects.
  - Every function is deterministic.
  - Adding a new function requires only adding to FUNCTION_REGISTRY.
  - Trigonometric functions operate in RADIANS.

Dependencies: none (only stdlib math)
"""

import math
from typing import Callable

from .errors import DomainError, UnknownFunctionError


# ---------------------------------------------------------------------------
# Safe wrapper helpers
# ---------------------------------------------------------------------------

def _safe_sqrt(x: float) -> float:
    if x < 0:
        raise DomainError("sqrt", x)
    return math.sqrt(x)


def _safe_asin(x: float) -> float:
    if not (-1.0 <= x <= 1.0):
        raise DomainError("asin", x)
    return math.asin(x)


def _safe_acos(x: float) -> float:
    if not (-1.0 <= x <= 1.0):
        raise DomainError("acos", x)
    return math.acos(x)


def _safe_log(x: float) -> float:
    if x <= 0:
        raise DomainError("log", x)
    return math.log(x)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

FUNCTION_REGISTRY: dict[str, Callable[..., float]] = {
    # Arithmetic helpers
    "abs":  abs,
    "min":  min,
    "max":  max,
    "pow":  lambda a, b: float(a ** b),

    # Roots / powers
    "sqrt": _safe_sqrt,

    # Trigonometry (radians)
    "sin":  math.sin,
    "cos":  math.cos,
    "tan":  math.tan,
    "asin": _safe_asin,
    "acos": _safe_acos,
    "atan": math.atan,
    "atan2": math.atan2,

    # Logarithm (natural)
    "log":  _safe_log,

    # Rounding
    "floor": math.floor,
    "ceil":  math.ceil,
    "round": round,
}


def call(name: str, args: list[float]) -> float:
    """
    Dispatch a whitelisted function call.

    Raises:
        UnknownFunctionError: if the name is not in the whitelist.
        DomainError: if the function raises one internally.
    """
    if name not in FUNCTION_REGISTRY:
        raise UnknownFunctionError(name)
    return float(FUNCTION_REGISTRY[name](*args))


def is_known(name: str) -> bool:
    return name in FUNCTION_REGISTRY


# Exported for documentation / tooling
ALLOWED_FUNCTION_NAMES: frozenset[str] = frozenset(FUNCTION_REGISTRY.keys())
