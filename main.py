import sys
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6 import QtWidgets

from core.loader import load_mesh
from visualization.pv_display import show_mesh
from ui.main_window import MainWindow


def run_cli(path: str) -> None:
    tri_mesh, pv_mesh = load_mesh(path)
    show_mesh(pv_mesh, title=f"SmartDFM – {Path(path).name}")


def run_gui() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli(sys.argv[1])
    else:
        run_gui()