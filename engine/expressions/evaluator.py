"""
engine/expressions/evaluator.py

Deterministic, side-effect-free expression evaluator for the Cut-List Planner.

Supported syntax:
    Literals:     42, 3.14, .5
    Variables:    any identifier that resolves in the provided scope
    Arithmetic:   + - * /
    Power:        ^ or pow(a, b)
    Grouping:     ( )
    Functions:    whitelisted set — see functions.ALLOWED_FUNCTION_NAMES
    Unary minus:  -x

Grammar (EBNF):
    expression   = additive
    additive     = multiplicative ( ('+' | '-') multiplicative )*
    multiplicative = power ( ('*' | '/') power )*
    power        = unary ( '^' unary )*        # right-associative
    unary        = '-' unary | primary
    primary      = NUMBER
                 | IDENT '(' arglist ')'
                 | IDENT
                 | '(' expression ')'
    arglist      = expression ( ',' expression )*

Design invariants:
    - No global or mutable state.
    - Every public function is a pure function.
    - Unknown variables → UndefinedVariableError (never silently zero).
    - Unknown functions → UnknownFunctionError.
    - Division by zero → DivisionByZeroError.
    - Out-of-domain math → DomainError (propagated from functions module).

Dependencies:
    engine.expressions.functions
    engine.expressions.errors
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

from .errors import (
    DivisionByZeroError,
    EvaluationError,
    ParseError,
    UndefinedVariableError,
    UnknownFunctionError,
)
from . import functions as fn

# ---------------------------------------------------------------------------
# Scope type
# ---------------------------------------------------------------------------

Scope = dict[str, float]


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<SKIP>    \s+                   )   # whitespace to skip
  | (?P<NUMBER>  \d+\.?\d* | \.\d+    )   # integer or decimal literal
  | (?P<IDENT>   [A-Za-z_]\w*         )   # identifier / function name
  | (?P<OP>      [+\-*/^(),]          )   # operators and punctuation
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str   # 'NUMBER' | 'IDENT' | 'OP' | 'EOF'
    value: str
    pos: int


def _tokenise(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    length = len(text)
    while pos < length:
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(f"Unexpected character '{text[pos]}'", text)
        pos = m.end()
        if m.lastgroup == "SKIP":
            continue
        tokens.append(Token(kind=m.lastgroup, value=m.group(), pos=m.start()))
    tokens.append(Token(kind="EOF", value="", pos=len(text)))
    return tokens


# ---------------------------------------------------------------------------
# Recursive-descent parser / evaluator
# ---------------------------------------------------------------------------

class _Parser:
    """
    Evaluates an expression string in a single pass (parse + eval fused).
    Not thread-safe per instance; create one per evaluate() call.
    """

    def __init__(self, tokens: list[Token], scope: Scope, raw: str):
        self._tokens = tokens
        self._pos = 0
        self._scope = scope
        self._raw = raw   # kept for error messages

    # --- token stream helpers ---

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _consume(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str, value: str | None = None) -> Token:
        tok = self._consume()
        if tok.kind != kind or (value is not None and tok.value != value):
            expected = f"'{value}'" if value else kind
            raise ParseError(f"Expected {expected}, got '{tok.value}'", self._raw)
        return tok

    # --- grammar rules ---

    def parse(self) -> float:
        result = self._additive()
        if self._peek().kind != "EOF":
            raise ParseError(
                f"Unexpected token '{self._peek().value}' after expression", self._raw
            )
        return result

    def _additive(self) -> float:
        left = self._multiplicative()
        while self._peek().kind == "OP" and self._peek().value in ("+", "-"):
            op = self._consume().value
            right = self._multiplicative()
            if op == "+":
                left += right
            else:
                left -= right
        return left

    def _multiplicative(self) -> float:
        left = self._power()
        while self._peek().kind == "OP" and self._peek().value in ("*", "/"):
            op = self._consume().value
            right = self._power()
            if op == "/":
                if right == 0.0:
                    raise DivisionByZeroError(self._raw)
                left /= right
            else:
                left *= right
        return left

    def _power(self) -> float:
        """Right-associative: a^b^c = a^(b^c)."""
        base = self._unary()
        if self._peek().kind == "OP" and self._peek().value == "^":
            self._consume()
            exp = self._power()   # right-recursion
            return float(base ** exp)
        return base

    def _unary(self) -> float:
        if self._peek().kind == "OP" and self._peek().value == "-":
            self._consume()
            return -self._unary()
        return self._primary()

    def _primary(self) -> float:
        tok = self._peek()

        if tok.kind == "NUMBER":
            self._consume()
            return float(tok.value)

        if tok.kind == "IDENT":
            self._consume()
            name = tok.value
            # Function call?
            if self._peek().kind == "OP" and self._peek().value == "(":
                return self._function_call(name)
            # Variable reference
            if name not in self._scope:
                raise UndefinedVariableError(name, self._raw)
            return float(self._scope[name])

        if tok.kind == "OP" and tok.value == "(":
            self._consume()
            val = self._additive()
            self._expect("OP", ")")
            return val

        raise ParseError(f"Unexpected token '{tok.value}'", self._raw)

    def _function_call(self, name: str) -> float:
        if not fn.is_known(name):
            raise UnknownFunctionError(name, self._raw)
        self._expect("OP", "(")
        args: list[float] = []
        if not (self._peek().kind == "OP" and self._peek().value == ")"):
            args.append(self._additive())
            while self._peek().kind == "OP" and self._peek().value == ",":
                self._consume()
                args.append(self._additive())
        self._expect("OP", ")")
        return fn.call(name, args)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(expression: str, scope: Scope | None = None) -> float:
    """
    Evaluate *expression* as a real-valued formula.

    Parameters
    ----------
    expression:
        The formula string, e.g. ``"2 * width + sqrt(height^2 + depth^2)"``.
    scope:
        Mapping of variable names → numeric values.
        If None, an empty scope is used (only literals and constants allowed).

    Returns
    -------
    float
        The computed result.

    Raises
    ------
    ParseError           — syntax error
    UndefinedVariableError — expression references an unknown variable
    UnknownFunctionError   — expression calls a non-whitelisted function
    DivisionByZeroError    — explicit division by zero
    DomainError            — math function domain violation (e.g. sqrt(-1))
    """
    if scope is None:
        scope = {}
    tokens = _tokenise(expression)
    parser = _Parser(tokens, scope, expression)
    return parser.parse()


def evaluate_safe(expression: str, scope: Scope | None = None) -> tuple[float | None, str | None]:
    """
    Like :func:`evaluate` but catches all :class:`ExpressionError` subclasses.

    Returns
    -------
    (value, None)   on success
    (None, message) on any ExpressionError
    """
    try:
        return evaluate(expression, scope), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
