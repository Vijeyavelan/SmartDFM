# ui/main_window.py

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QFileDialog,
    QMessageBox,
    QToolBar,
    QStatusBar,
)
from PySide6.QtCore import Qt, Slot

# If you want to actually load a mesh when opening a file,
# you can uncomment these lines (once everything imports correctly):
# from core.loader import load_mesh
# from visualization.pv_display import show_mesh


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- Basic window setup (light, won't freeze) ---
        self.setWindowTitle("SmartDFM")
        self.resize(1200, 800)

        # Track current file path
        self.current_mesh_path: Path | None = None

        # UI building (all lightweight)
        self._create_central_widget()
        self._create_toolbar()
        self._create_statusbar()

    # ---------------- Central widget ---------------- #

    def _create_central_widget(self) -> None:
        """Create the main central widget with a simple placeholder."""
        central = QWidget(self)
        layout = QVBoxLayout(central)

        self.info_label = QLabel(
            "Welcome to SmartDFM\n\n"
            "Use the toolbar or File menu to open an STL file.",
            central,
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.info_label)
        central.setLayout(layout)

        self.setCentralWidget(central)

    # ---------------- Toolbar & Statusbar ---------------- #

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Open action
        open_action = toolbar.addAction("Open STL")
        open_action.triggered.connect(self.open_mesh_dialog)

        # You can add more actions here later (Run DFM, Orientation, etc.)

    def _create_statusbar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.statusBar().showMessage("Ready")

    # ---------------- File handling ---------------- #

    @Slot()
    def open_mesh_dialog(self) -> None:
        """Show a file dialog to select an STL and then load it."""
        # macOS-friendly dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open STL file",
            "",
            "STL Files (*.stl);;All Files (*)",
        )

        if not file_path:
            return  # user cancelled

        self.current_mesh_path = Path(file_path)
        self.statusBar().showMessage(f"Loaded: {self.current_mesh_path.name}")

        # For now, just show the file name in the label.
        # Later we will hook in the DFM logic + viewer.
        self.info_label.setText(
            f"Loaded mesh:\n{self.current_mesh_path}\n\n"
            "DFM analysis and 3D viewer will appear here later."
        )

        # If you want to also pop up the PyVista window (CLI-style viewer),
        # you can UNCOMMENT this once imports work:
        #
        # try:
        #     tri_mesh, pv_mesh = load_mesh(str(self.current_mesh_path))
        #     show_mesh(pv_mesh, title=f"SmartDFM – {self.current_mesh_path.name}")
        # except Exception as e:
        #     QMessageBox.critical(self, "Error", f"Failed to load mesh:\n{e}")
        #     self.statusBar().showMessage("Failed to load mesh")