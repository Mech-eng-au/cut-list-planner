"""
cut_list_planner/__main__.py

Entry point:  python -m cut_list_planner [--debug] [path/to/project.toml]

Flags
-----
--debug         Set log level to DEBUG (verbose).  Can also be activated
                with the environment variable CUT_LIST_DEBUG=1.
"""
import os
import sys
from pathlib import Path

# Add the package directory itself to sys.path so that
# 'engine', 'state', 'ui', 'log' are all importable regardless of
# where the user runs python from.
sys.path.insert(0, str(Path(__file__).parent))

# --- logging must be the very first thing configured ---
from log import setup as log_setup

debug_mode = (
    "--debug" in sys.argv
    or os.environ.get("CUT_LIST_DEBUG", "").strip() not in ("", "0")
)
# Remove --debug from argv before anything else sees it.
args = [a for a in sys.argv[1:] if a != "--debug"]

log_setup(debug=debug_mode)

# --- now safe to import the rest of the package ---
import ui.app

project_path = args[0] if args else None
ui.app.CutListApp(project_path=project_path).run()