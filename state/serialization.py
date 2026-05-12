"""
state/serialization.py

Save and load Project objects as TOML files.

Format
------
[project]
name = "My Frame"

[stock]
length_mm = 6000.0
width_mm  = 90.0
height_mm = 45.0
kerf_mm   = 3.0

[[variables]]
name    = "height"
formula = "2000"

[[parts]]
label       = "Vertical"
length_expr = "height"
quantity    = 2

Dependencies: stdlib tomllib (Python >= 3.11) with tomli fallback
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

from .models import Part, Project, StockBar, Variable


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save(project: Project, path: str | Path) -> None:
    """Serialise *project* to a TOML file at *path*."""
    path = Path(path)
    lines: list[str] = []

    lines += [
        "[project]",
        f'name = "{project.name}"',
        "",
        "[stock]",
        f"length_mm = {project.stock.length_mm}",
        f"width_mm  = {project.stock.width_mm}",
        f"height_mm = {project.stock.height_mm}",
        f"kerf_mm   = {project.stock.kerf_mm}",
        "",
    ]

    for v in project.variables:
        lines += [
            "[[variables]]",
            f'name    = "{v.name}"',
            f'formula = "{v.formula}"',
            "",
        ]

    for p in project.parts:
        lines += [
            "[[parts]]",
            f'label       = "{p.label}"',
            f'length_expr = "{p.length_expr}"',
            f"quantity    = {p.quantity}",
            "",
        ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load(path: str | Path) -> Project:
    """Load a Project from a TOML file."""
    path = Path(path)

    if tomllib is None:
        raise RuntimeError(
            "TOML support requires Python 3.11+ or 'pip install tomli'.\n"
            "Run: pip install tomli"
        )

    with open(path, "rb") as f:
        data = tomllib.load(f)

    name = data.get("project", {}).get("name", path.stem)

    stock_data = data.get("stock", {})
    stock = StockBar(
        length_mm=float(stock_data.get("length_mm", 6000.0)),
        width_mm=float(stock_data.get("width_mm",  50.0)),
        height_mm=float(stock_data.get("height_mm", 50.0)),
        kerf_mm=float(stock_data.get("kerf_mm",   3.0)),
    )

    variables = [
        Variable(name=v["name"], formula=v["formula"])
        for v in data.get("variables", [])
    ]

    parts = [
        Part(
            label=p["label"],
            length_expr=p["length_expr"],
            quantity=int(p.get("quantity", 1)),
        )
        for p in data.get("parts", [])
    ]

    return Project(name=name, stock=stock, variables=variables, parts=parts)


# ---------------------------------------------------------------------------
# Example project writer
# ---------------------------------------------------------------------------

EXAMPLE_TOML = """\
[project]
name = "Braced Steel Frame"

[stock]
length_mm = 6000.0
width_mm  = 90.0
height_mm = 45.0
kerf_mm   = 3.0

[[variables]]
name    = "height"
formula = "2000"

[[variables]]
name    = "width"
formula = "1200"

[[variables]]
name    = "brace"
formula = "sqrt(height^2 + width^2)"

[[parts]]
label       = "Vertical"
length_expr = "height"
quantity    = 4

[[parts]]
label       = "Horizontal"
length_expr = "width"
quantity    = 3

[[parts]]
label       = "Diagonal brace"
length_expr = "brace"
quantity    = 2
"""


def write_example(path: str | Path) -> None:
    """Write the built-in example project to *path*."""
    Path(path).write_text(EXAMPLE_TOML, encoding="utf-8")
