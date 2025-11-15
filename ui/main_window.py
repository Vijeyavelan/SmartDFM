"""Main PyQt6 window skeleton for SmartDFM with embedded PyVista viewer."""

from pathlib import Path
from typing import Optional

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QAction

from core.loader import load_mesh
from ui.viewer_widget import ViewerWidget


class MainWindow(QtWidgets.QMainWindow):
    """Main window for SmartDFM.

    Layout:
      - Left: simple info panel (later: controls, buttons, etc.)
      - Right: embedded 3D viewer (PyVista QtInteractor)
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SmartDFM")
        self.resize(1200, 800)

        self.tri_mesh = None
        self.pv_mesh = None
        self.current_mesh_path: Optional[str] = None

        central = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        # --- Left panel (info + later DFM controls) ---
        left_panel = QtWidgets.QFrame(self)
        left_panel.setFrameStyle(
            QtWidgets.QFrame.Shape.StyledPanel | QtWidgets.QFrame.Shadow.Raised
        )
        left_layout = QtWidgets.QVBoxLayout(left_panel)

        label = QtWidgets.QLabel(
            "SmartDFM\n\n"
            "1. Use File → Open Mesh… to load an STL/OBJ/PLY.\n"
            "2. The 3D view on the right will update.\n"
            "3. Later: buttons for thickness, draft angle, etc. will appear here.",
            self,
        )
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        label.setWordWrap(True)
        left_layout.addWidget(label)
        left_layout.addStretch(1)

        # --- Right panel (embedded viewer) ---
        self.viewer = ViewerWidget(self)

        # --- Assemble layout ---
        main_layout.addWidget(left_panel, 0)   # left panel takes minimal width
        main_layout.addWidget(self.viewer, 1)  # viewer expands

        self.setCentralWidget(central)
        self._create_menu()

    def _create_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open Mesh…", self)
        open_action.triggered.connect(self.on_open_mesh)
        file_menu.addAction(open_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QtWidgets.QApplication.instance().quit)
        file_menu.addAction(quit_action)

    def on_open_mesh(self) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setNameFilter("Mesh files (*.stl *.obj *.ply)")
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            path = dialog.selectedFiles()[0]
            self.load_and_show_mesh(path)

    def load_and_show_mesh(self, path: str) -> None:
        """Load a mesh and display it in the embedded viewer."""
        self.tri_mesh, self.pv_mesh = load_mesh(path)
        self.current_mesh_path = path

        self.viewer.set_pv_mesh(self.pv_mesh)
        self.setWindowTitle(f"SmartDFM – {Path(path).name}")