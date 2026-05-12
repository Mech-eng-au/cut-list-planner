"""
engine/expressions/errors.py

All error types raised by the expression evaluator subsystem.
No dependencies on other engine modules.
"""


class ExpressionError(Exception):
    """Base class for all expression evaluation errors."""
    pass


class ParseError(ExpressionError):
    """Raised when an expression cannot be parsed (syntax error)."""
    def __init__(self, message: str, expression: str = ""):
        self.expression = expression
        super().__init__(f"Parse error in '{expression}': {message}" if expression else f"Parse error: {message}")


class EvaluationError(ExpressionError):
    """Raised when a syntactically valid expression fails at evaluation time."""
    def __init__(self, message: str, expression: str = ""):
        self.expression = expression
        super().__init__(f"Evaluation error in '{expression}': {message}" if expression else f"Evaluation error: {message}")


class UndefinedVariableError(EvaluationError):
    """Raised when an expression references a variable that is not in scope."""
    def __init__(self, variable_name: str, expression: str = ""):
        self.variable_name = variable_name
        super().__init__(f"Undefined variable: '{variable_name}'", expression)


class UnknownFunctionError(EvaluationError):
    """Raised when an expression calls a function not in the whitelist."""
    def __init__(self, function_name: str, expression: str = ""):
        self.function_name = function_name
        super().__init__(
            f"Unknown function: '{function_name}'. "
            f"Only whitelisted functions are allowed.", expression
        )


class DivisionByZeroError(EvaluationError):
    """Raised on division by zero."""
    def __init__(self, expression: str = ""):
        super().__init__("Division by zero", expression)


class DomainError(EvaluationError):
    """Raised when a math function receives an out-of-domain argument (e.g. sqrt(-1))."""
    def __init__(self, function_name: str, argument: float, expression: str = ""):
        self.function_name = function_name
        self.argument = argument
        super().__init__(
            f"Domain error: {function_name}({argument}) is undefined in ℝ", expression
        )
