# ui/main_window.py

import sys
import numpy as np

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMenuBar,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QPushButton
)
from PySide6.QtGui import QAction

import pyqtgraph as pg
import pyqtgraph.opengl as gl

from core.stl_loader import load_stl
from core.dfm_checks import run_all_checks


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SmartDFM - STL Viewer")
        self.resize(1200, 800)

        # ---- Status bar ----
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # ---- Central widget ----
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Root vertical layout (button bar on top, content below)
        root_layout = QVBoxLayout(central_widget)

        # ---- Top button bar ----
        button_bar = QHBoxLayout()
        self.open_button = QPushButton("Open STL…")
        self.open_button.clicked.connect(self.open_stl_dialog)
        button_bar.addWidget(self.open_button)
        button_bar.addStretch()
        root_layout.addLayout(button_bar)

        # ---- Content layout: 3D view (left) + DFM panel (right) ----
        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout)

        # ---- 3D View ----
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((0.9, 0.9, 0.9, 1.0))
        self.view.opts['distance'] = 40
        content_layout.addWidget(self.view, stretch=4)

        # Add a basic grid so you see orientation
        grid = gl.GLGridItem()
        grid.setSize(20, 20)
        grid.setSpacing(1, 1)
        self.view.addItem(grid)

        # Store current mesh item
        self.mesh_item = None

        # ---- Right-side DFM panel ----
        self.dfm_panel = QWidget()
        dfm_layout = QVBoxLayout(self.dfm_panel)

        self.lbl_title = QLabel("<b>DFM Summary</b>")
        dfm_layout.addWidget(self.lbl_title)

        # Global thickness labels
        self.lbl_global_status = QLabel("Global Thickness: -")
        self.lbl_global_value = QLabel("Smallest Dimension: -")
        dfm_layout.addWidget(self.lbl_global_status)
        dfm_layout.addWidget(self.lbl_global_value)

        # Local thickness labels
        self.lbl_local_status = QLabel("Local Thickness: -")
        self.lbl_local_min = QLabel("Min Local Thickness: -")
        self.lbl_local_thin_count = QLabel("Thin Vertices: -")
        dfm_layout.addWidget(self.lbl_local_status)
        dfm_layout.addWidget(self.lbl_local_min)
        dfm_layout.addWidget(self.lbl_local_thin_count)

        # DFM results table
        self.dfm_table = QTableWidget()
        self.dfm_table.setColumnCount(2)
        self.dfm_table.setHorizontalHeaderLabels(["Check", "Result"])
        self.dfm_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        dfm_layout.addWidget(self.dfm_table)

        dfm_layout.addStretch()
        content_layout.addWidget(self.dfm_panel, stretch=2)

        # ---- Menu bar ----
        self._create_menu()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _create_menu(self):
        menubar = self.menuBar() or QMenuBar(self)
        self.setMenuBar(menubar)

        file_menu = menubar.addMenu("&File")

        open_action = QAction("Open STL...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_stl_dialog)

        file_menu.addAction(open_action)

    # ------------------------------------------------------------------
    # File open
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # DFM panel update
    # ------------------------------------------------------------------
    def update_dfm_panel(self, dfm_results: dict):
        """Update the right-side DFM summary panel and table."""
        checks = dfm_results.get("checks", {})

        global_info = checks.get("global_thickness", {})
        local_info = checks.get("local_thickness", {})

        g_status = global_info.get("status", "-")
        g_smallest = global_info.get("smallest_dimension", "-")

        l_status = local_info.get("status", "-")
        l_min = local_info.get("min_thickness", "-")
        l_count = local_info.get("num_thin_vertices", "-")

        # Labels
        self.lbl_global_status.setText(f"Global Thickness: {g_status}")
        self.lbl_global_value.setText(f"Smallest Dimension: {g_smallest}")

        self.lbl_local_status.setText(f"Local Thickness: {l_status}")
        self.lbl_local_min.setText(f"Min Local Thickness: {l_min}")
        self.lbl_local_thin_count.setText(f"Thin Vertices: {l_count}")

        # Table
        self.dfm_table.setRowCount(0)

        def add_row(name, value):
            row = self.dfm_table.rowCount()
            self.dfm_table.insertRow(row)
            self.dfm_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.dfm_table.setItem(row, 1, QTableWidgetItem(str(value)))

        add_row("Global Status", g_status)
        add_row("Smallest Dimension", g_smallest)
        add_row("Local Status", l_status)
        add_row("Min Local Thickness", l_min)
        add_row("Thin Vertices", l_count)

    # ------------------------------------------------------------------
    # Load, DFM, and display
    # ------------------------------------------------------------------
    def load_and_display_stl(self, file_path: str):
        """
        Load STL, run DFM checks, and display mesh.
        Thin regions (by local wall thickness) are colored red.
        """
        try:
            # ---- Load STL geometry ----
            vertices, faces = load_stl(file_path)

            if vertices.size == 0 or faces.size == 0:
                raise ValueError("STL file contains no geometry.")

            # ---- Basic model info BEFORE centering/scaling ----
            tri_count = faces.shape[0]
            min_bounds = vertices.min(axis=0)
            max_bounds = vertices.max(axis=0)
            extents = max_bounds - min_bounds

            # ---- Run DFM pipeline ----
            dfm_results = run_all_checks(vertices, faces)
            dfm_summary = dfm_results.get("summary", "DFM: no summary")
            checks = dfm_results.get("checks", {})

            # Update right-side DFM panel
            self.update_dfm_panel(dfm_results)

            local_chk = checks.get("local_thickness", {})
            global_chk = checks.get("global_thickness", {})

            per_vertex_thickness = local_chk.get("per_vertex_thickness", None)
            threshold = local_chk.get("threshold", None)

            # ---- Center + normalize for display ----
            center = vertices.mean(axis=0)
            vertices_centered = vertices - center

            max_extent = np.abs(vertices_centered).max()
            if max_extent > 0:
                vertices_centered = vertices_centered / max_extent * 10.0

            # ---- Build per-vertex colors (grey default, red if thin) ----
            vertex_colors = None
            if per_vertex_thickness is not None and threshold is not None:
                t = np.array(per_vertex_thickness, dtype=float)

                # Start with all grey
                vertex_colors = np.zeros((vertices.shape[0], 4), dtype=float)
                vertex_colors[:, :] = [0.7, 0.7, 0.7, 1.0]  # RGBA grey

                finite = np.isfinite(t)
                thin_mask = finite & (t < threshold)
                # Thin vertices -> red
                vertex_colors[thin_mask] = [1.0, 0.0, 0.0, 1.0]

            # ---- Create mesh data (with optional vertex colors) ----
            mesh_data = gl.MeshData(
                vertexes=vertices_centered,
                faces=faces,
                vertexColors=vertex_colors
            )

            # Remove old mesh item if exists
            if self.mesh_item is not None:
                self.view.removeItem(self.mesh_item)

            # ---- Create mesh item ----
            self.mesh_item = gl.GLMeshItem(
                meshdata=mesh_data,
                smooth=False,
                drawFaces=True,
                drawEdges=True,
                edgeColor=(0, 0, 0, 1.0),
            )
            self.view.addItem(self.mesh_item)

            # ---- Show DFM warnings as popups ----
            if global_chk and global_chk.get("status") == "WARNING":
                QMessageBox.warning(
                    self,
                    "DFM Warning – Global Thickness",
                    global_chk.get("message", "Global thickness issue detected."),
                )

            if local_chk and local_chk.get("status") == "WARNING":
                QMessageBox.warning(
                    self,
                    "DFM Warning – Local Wall Thickness",
                    local_chk.get("message", "Local wall thickness issue detected."),
                )

            # ---- Update status bar ----
            if hasattr(self, "status"):
                msg = (
                    f"Loaded: {file_path.split('/')[-1]}  |  "
                    f"Triangles: {tri_count}  |  "
                    f"Size (X×Y×Z): "
                    f"{extents[0]:.2f} × {extents[1]:.2f} × {extents[2]:.2f} (model units)  |  "
                    f"{dfm_summary}"
                )
                self.status.showMessage(msg)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading STL",
                f"An error occurred while loading the STL file:\n\n{str(e)}",
            )
            if hasattr(self, "status"):
                self.status.showMessage(f"Error loading STL: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())