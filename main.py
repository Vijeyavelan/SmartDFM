"""Entry point for SmartDFM.

Currently supports:
- Optional CLI argument: mesh path to visualize
- If no path is given, opens the PyQt6 UI

Run:
    python main.py path/to/part.stl
or:
    python main.py
"""

import sys
from pathlib import Path

from PyQt6 import QtWidgets

from core.loader import load_mesh
from visualization.pv_display import show_mesh
from ui.main_window import MainWindow


def run_cli(path: str) -> None:
    """Run a simple CLI-based viewer using PyVista only."""
    tri_mesh, pv_mesh = load_mesh(path)
    show_mesh(pv_mesh, title=f"SmartDFM – {Path(path).name}")


def run_gui() -> None:
    """Run the PyQt6 GUI."""
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli(sys.argv[1])
    else:
        run_gui()
