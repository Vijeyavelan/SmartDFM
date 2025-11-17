# ui/main_window.py

import sys
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget,
    QVBoxLayout, QFileDialog, QMenuBar, QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

import pyqtgraph as pg
import pyqtgraph.opengl as gl

from core.stl_loader import load_stl


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SmartDFM - STL Viewer")
        self.resize(800, 600)

                # ---- Status bar ----
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # ---- Central widget + layout ----
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # ---- Top button bar ----
        button_bar = QHBoxLayout()
        self.open_button = QPushButton("Open STL…")
        self.open_button.clicked.connect(self.open_stl_dialog)
        button_bar.addWidget(self.open_button)
        button_bar.addStretch()
        layout.addLayout(button_bar)

        # ---- 3D View ----
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((0.9,0.9,0.9,1.0))
        self.view.opts['distance'] = 40
        layout.addWidget(self.view)

        # Add a basic grid so you see orientation
        grid = gl.GLGridItem()
        grid.setSize(20, 20)
        grid.setSpacing(1, 1)
        self.view.addItem(grid)

        # Store current mesh item
        self.mesh_item = None

        # ---- Menu bar ----
        self._create_menu()

    def _create_menu(self):
        menubar = self.menuBar() or QMenuBar(self)
        self.setMenuBar(menubar)

        file_menu = menubar.addMenu("&File")

        open_action = QAction("Open STL...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_stl_dialog)

        file_menu.addAction(open_action)

    def open_stl_dialog(self):
        """
        Open a file dialog to choose STL and then load + display it.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open STL File",
            "",
            "STL Files (*.stl);;All Files (*.*)"
        )

        if not file_path:
            return  # user cancelled

        self.load_and_display_stl(file_path)

    def load_and_display_stl(self, file_path: str):
        try:
            vertices, faces = load_stl(file_path)
        except Exception as e:
            print(f"Error loading STL: {e}")
            if hasattr(self, "status"):
                self.status.showMessage(f"Error loading STL: {e}")
            return

        # ---- Compute model info BEFORE centering/scaling ----
        tri_count = faces.shape[0]

        min_bounds = vertices.min(axis=0)   # [min_x, min_y, min_z]
        max_bounds = vertices.max(axis=0)   # [max_x, max_y, max_z]
        extents = max_bounds - min_bounds   # [size_x, size_y, size_z]

        # ---- Center + normalize for display ----
        center = vertices.mean(axis=0)
        vertices_centered = vertices - center

        max_extent = np.abs(vertices_centered).max()
        if max_extent > 0:
            vertices_centered = vertices_centered / max_extent * 10.0

        # Prepare mesh data
        mesh_data = gl.MeshData(vertexes=vertices_centered, faces=faces)

        # Remove old mesh item if exists
        if self.mesh_item is not None:
            self.view.removeItem(self.mesh_item)

        # Create new mesh item (with faces + edges)
        self.mesh_item = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            color=(0.7, 0.7, 0.7, 1.0),   # light gray faces
            drawFaces=True,
            drawEdges=True,
            edgeColor=(0, 0, 0, 1.0)
        )

        self.view.addItem(self.mesh_item)

        # ---- Update status bar ----
        if hasattr(self, "status"):
            msg = (
                f"Loaded: {file_path.split('/')[-1]}  |  "
                f"Triangles: {tri_count}  |  "
                f"Size (X×Y×Z): "
                f"{extents[0]:.2f} × {extents[1]:.2f} × {extents[2]:.2f} (model units)"
            )
            self.status.showMessage(msg)

# Only needed if you run this file directly for testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1000, 800)
    window.show()
    sys.exit(app.exec())