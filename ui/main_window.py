# ui/main_window.py

import sys
import os
import numpy as np

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMenuBar,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QPushButton, QDoubleSpinBox, QComboBox, QCheckBox,
    QFrame, QScrollArea, QToolButton, QButtonGroup, QStackedWidget
)
from PySide6.QtGui import QAction
from PySide6.QtGui import QGuiApplication
import pyqtgraph.opengl as gl

from core.stl_loader import load_stl
from core.dfm_engine import run_all_checks
from core.dfm_checks.thickness import (
    MIN_GLOBAL_THICKNESS,
    LOCAL_MIN_THICKNESS,
)
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SmartDFM - STL Viewer (Injection Molding DFM)")

        # 🔽 replace old self.resize(...) with this block
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width  = int(screen.width() * 0.75)   # 75% of screen width
        height = int(screen.height() * 0.75)  # 75% of screen height
        self.resize(width, height)

        # center the window on screen
        self.move(
            screen.x() + (screen.width() - width) // 2,
            screen.y() + (screen.height() - height) // 2,
        )

        # ---- Status bar ----
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # Store last analysis and file path (for export + re-run)
        self.last_dfm_results = None
        self.last_file_path = None
        # Which DFM issue is currently highlighted in 3D
        # (None = no special highlighting)
        self.active_visual_check = None

        # ---- Central widget ----
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Root vertical layout (button bar on top, content below)
        root_layout = QVBoxLayout(central_widget)


        # ---- Top feature mode bar (tab-like) ----
        self.feature_buttons = {}
        self.feature_button_group = QButtonGroup(self)
        self.feature_button_group.setExclusive(True)

        feature_bar_widget = QWidget()
        feature_bar_layout = QHBoxLayout(feature_bar_widget)
        feature_bar_layout.setContentsMargins(0, 0, 0, 0)
        feature_bar_layout.setSpacing(6)

        def add_feature_button(key: str, label: str):
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda checked, k=key: self.on_feature_tab_clicked(k))
            feature_bar_layout.addWidget(btn)
            self.feature_button_group.addButton(btn)
            self.feature_buttons[key] = btn

        add_feature_button("open", "Open")
        add_feature_button("home", "Home")
        add_feature_button("thickness", "Wall Thickness")
        add_feature_button("sharp", "Sharp Corners")
        add_feature_button("draft", "Draft Angle")
        add_feature_button("undercuts", "Undercuts")
        add_feature_button("rib_boss", "Rib/Boss")
        add_feature_button("export", "Export DFM")

        # default selected = OPEN
        self.feature_buttons["home"].setChecked(True)
        feature_bar_layout.addStretch()
        root_layout.addWidget(feature_bar_widget)
        self.feature_buttons["open"].clicked.connect(self.open_stl_dialog)
        self.feature_buttons["export"].clicked.connect(self.export_dfm_report)
        # ---- Content layout: 3D view (left) + Right feature stack (right) ----
        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout)

        # ---- 3D View ----
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((0.05, 0.05, 0.05, 1.0))
        self.view.opts["distance"] = 40
        content_layout.addWidget(self.view, stretch=4)

        # Add a basic grid so you see orientation
        grid = gl.GLGridItem()
        grid.setSize(30, 30)
        grid.setSpacing(1, 1)
        self.view.addItem(grid)

        # --- Fixed XYZ axis at one corner of the grid ---
        # Grid spans roughly -10..+10 in X/Y (size=20), so use a corner near (-10, -10, 0)
        axis_origin = np.array([-15.0, -15.0, 0.0], dtype=float)  # slightly inside the grid edge
        axis_len = 3.0  # length of each axis line

        # X axis: red
        x_axis_pos = np.array([
            axis_origin,
            axis_origin + np.array([axis_len, 0.0, 0.0], dtype=float)
        ])
        self.grid_axis_x = gl.GLLinePlotItem(
            pos=x_axis_pos,
            color=(1.0, 0.0, 0.0, 1.0),
            width=3,
            antialias=True,
        )
        self.view.addItem(self.grid_axis_x)

        # Y axis: green
        y_axis_pos = np.array([
            axis_origin,
            axis_origin + np.array([0.0, axis_len, 0.0], dtype=float)
        ])
        self.grid_axis_y = gl.GLLinePlotItem(
            pos=y_axis_pos,
            color=(0.0, 1.0, 0.0, 1.0),
            width=3,
            antialias=True,
        )
        self.view.addItem(self.grid_axis_y)

        # Z axis: blue
        z_axis_pos = np.array([
            axis_origin,
            axis_origin + np.array([0.0, 0.0, axis_len], dtype=float)
        ])
        self.grid_axis_z = gl.GLLinePlotItem(
            pos=z_axis_pos,
            color=(0.0, 0.0, 1.0, 1.0),
            width=3,
            antialias=True,
        )
        self.view.addItem(self.grid_axis_z)

        # --- Axis legend labels (screen overlay) ---
        self.axis_label_x = QLabel("X", self)
        self.axis_label_x.setStyleSheet("color: red; font-weight: bold;")
        self.axis_label_x.adjustSize()

        self.axis_label_y = QLabel("Y", self)
        self.axis_label_y.setStyleSheet("color: green; font-weight: bold;")
        self.axis_label_y.adjustSize()

        self.axis_label_z = QLabel("Z", self)
        self.axis_label_z.setStyleSheet("color: blue; font-weight: bold;")
        self.axis_label_z.adjustSize()

        # make sure they draw above other widgets
        self.axis_label_x.raise_()
        self.axis_label_y.raise_()
        self.axis_label_z.raise_()

        # Store current mesh item
        self.mesh_item = None

        # ---- Right-side DFM panel (this becomes the OPEN page content) ----
        self.dfm_panel = QWidget()
        dfm_layout = QVBoxLayout(self.dfm_panel)

        # Scroll wrapper so panel never gets cut off
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.dfm_panel)
        scroll.setMinimumWidth(320)
        scroll.setMaximumWidth(420)

        # --- SECTION 0: Title ---
        self.lbl_title = QLabel("<b>Injection Molding DFM Summary</b>")
        dfm_layout.addWidget(self.lbl_title)
        dfm_layout.addSpacing(6)


        # ---- Right side: stacked pages for each feature ----
        self.feature_stack = QStackedWidget()
        self.feature_page_indices = {}

        # HOME page: simple Part Info panel
        self.page_home = QWidget()
        layout_home = QVBoxLayout(self.page_home)
        layout_home.setContentsMargins(10, 10, 10, 10)
        layout_home.setSpacing(6)

        self.home_part_header = QLabel("<b>Part Info</b>")
        self.home_file_label = QLabel("File: -")
        self.home_triangles_label = QLabel("Triangles: -")
        self.home_size_label = QLabel("Size (X×Y×Z): -")

        layout_home.addWidget(self.home_part_header)
        layout_home.addSpacing(6)
        layout_home.addWidget(self.home_file_label)
        layout_home.addWidget(self.home_triangles_label)
        layout_home.addWidget(self.home_size_label)
        layout_home.addStretch()

        idx_home = self.feature_stack.addWidget(self.page_home)
        self.feature_page_indices["home"] = idx_home

        # OPEN / SUMMARY page wraps the existing scroll+dfm_panel
        self.page_open = QWidget()
        page_open_layout = QVBoxLayout(self.page_open)
        page_open_layout.setContentsMargins(0, 0, 0, 0)
        page_open_layout.setSpacing(0)
        page_open_layout.addWidget(scroll)

        idx_open = self.feature_stack.addWidget(self.page_open)
        self.feature_page_indices["open"] = idx_open

    # ------------------------------------------------------------------
    # WALL THICKNESS PAGE
    # ------------------------------------------------------------------
        self.page_thickness = QWidget()
        layout_thickness = QVBoxLayout(self.page_thickness)
        layout_thickness.setContentsMargins(10, 10, 10, 10)
        layout_thickness.setSpacing(6)

        thickness_header = QLabel("<b>Wall Thickness</b>")
        layout_thickness.addWidget(thickness_header)
        layout_thickness.addSpacing(6)

        # Global thickness threshold spin box
        global_row = QHBoxLayout()
        global_row.addWidget(QLabel("Global min thickness:"))
        self.spin_global = QDoubleSpinBox()
        self.spin_global.setDecimals(3)
        self.spin_global.setSingleStep(0.1)
        self.spin_global.setRange(0.01, 1000.0)
        self.spin_global.setValue(MIN_GLOBAL_THICKNESS)
        self.spin_global.valueChanged.connect(self.on_threshold_changed)
        global_row.addWidget(self.spin_global)
        layout_thickness.addLayout(global_row)

        # Local thickness threshold spin box
        local_row = QHBoxLayout()
        local_row.addWidget(QLabel("Local wall thickness:"))
        self.spin_local = QDoubleSpinBox()
        self.spin_local.setDecimals(3)
        self.spin_local.setSingleStep(0.1)
        self.spin_local.setRange(0.01, 1000.0)
        self.spin_local.setValue(LOCAL_MIN_THICKNESS)
        self.spin_local.valueChanged.connect(self.on_threshold_changed)
        local_row.addWidget(self.spin_local)
        layout_thickness.addLayout(local_row)

        layout_thickness.addSpacing(10)

        # Thickness-specific DFM overview (already added earlier)
        self.thickness_status_global = QLabel("Global Thickness: -")
        self.thickness_status_local = QLabel("Local Thickness: -")
        self.thickness_smallest_dim = QLabel("Smallest Dimension: -")
        self.thickness_min_local = QLabel("Min Local Thickness: -")
        self.thickness_thin_vertices = QLabel("Thin Vertices: -")

        layout_thickness.addWidget(self.thickness_status_global)
        layout_thickness.addWidget(self.thickness_status_local)
        layout_thickness.addWidget(self.thickness_smallest_dim)
        layout_thickness.addWidget(self.thickness_min_local)
        layout_thickness.addWidget(self.thickness_thin_vertices)

        # Thickness details table
        self.thickness_table = QTableWidget()
        self.thickness_table.setColumnCount(2)
        self.thickness_table.setHorizontalHeaderLabels(["Check", "Key Value"])
        self.thickness_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_thickness.addWidget(self.thickness_table)

        layout_thickness.addStretch()

        idx_thickness = self.feature_stack.addWidget(self.page_thickness)
        self.feature_page_indices["thickness"] = idx_thickness

    # ------------------------------------------------------------------
    # SHARP CORNERS PAGE
    # ------------------------------------------------------------------
        # Sharp Corners page
        self.page_sharp = QWidget()
        layout_sharp = QVBoxLayout(self.page_sharp)
        layout_sharp.setContentsMargins(10, 10, 10, 10)
        layout_sharp.setSpacing(6)

        sharp_header = QLabel("<b>Sharp Corners</b>")
        layout_sharp.addWidget(sharp_header)
        layout_sharp.addSpacing(6)

        # 🚩 These labels are ONLY for the Sharp Corners page
        self.sharp_status = QLabel("Sharp Corners: -")
        self.sharp_edge_count = QLabel("Sharp Edges: -")

        layout_sharp.addWidget(self.sharp_status)
        layout_sharp.addWidget(self.sharp_edge_count)

        # Sharp-corners-only details table
        self.sharp_table = QTableWidget()
        self.sharp_table.setColumnCount(2)
        self.sharp_table.setHorizontalHeaderLabels(["Check", "Key Value"])
        self.sharp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_sharp.addWidget(self.sharp_table)

        layout_sharp.addStretch()

        idx_sharp = self.feature_stack.addWidget(self.page_sharp)
        self.feature_page_indices["sharp"] = idx_sharp

    # ------------------------------------------------------------------
    # DRAFT ANGLE PAGE
    # ------------------------------------------------------------------
        self.page_draft = QWidget()
        layout_draft = QVBoxLayout(self.page_draft)
        layout_draft.setContentsMargins(10, 10, 10, 10)
        layout_draft.setSpacing(6)

        draft_header = QLabel("<b>Draft & Pull Direction</b>")
        layout_draft.addWidget(draft_header)
        layout_draft.addSpacing(6)

        # Pull direction selector
        pull_row = QHBoxLayout()
        pull_row.addWidget(QLabel("Pull direction:"))
        self.combo_pull = QComboBox()
        self.combo_pull.addItems(["+Z", "-Z", "+X", "-X", "+Y", "-Y"])
        self.combo_pull.setCurrentText("+Z")
        self.combo_pull.currentIndexChanged.connect(self.on_threshold_changed)
        pull_row.addWidget(self.combo_pull)
        layout_draft.addLayout(pull_row)

        layout_draft.addSpacing(10)

        # Draft-specific overview
        self.draft_status = QLabel("Draft Angle: -")
        self.draft_bad_faces = QLabel("Faces below min draft: -")

        layout_draft.addWidget(self.draft_status)
        layout_draft.addWidget(self.draft_bad_faces)

        self.draft_table = QTableWidget()
        self.draft_table.setColumnCount(2)
        self.draft_table.setHorizontalHeaderLabels(["Check", "Key Value"])
        self.draft_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_draft.addWidget(self.draft_table)

        layout_draft.addStretch()

        idx_draft = self.feature_stack.addWidget(self.page_draft)
        self.feature_page_indices["draft"] = idx_draft

    # ------------------------------------------------------------------
    # UNDERCUTS PAGE
    # ------------------------------------------------------------------
        self.page_undercuts = QWidget()
        layout_undercuts = QVBoxLayout(self.page_undercuts)
        layout_undercuts.setContentsMargins(10, 10, 10, 10)
        layout_undercuts.setSpacing(6)

        undercuts_header = QLabel("<b>Undercuts</b>")
        layout_undercuts.addWidget(undercuts_header)
        layout_undercuts.addSpacing(6)

        self.undercut_status = QLabel("Undercuts: -")
        self.undercut_faces = QLabel("Undercut Faces: -")

        layout_undercuts.addWidget(self.undercut_status)
        layout_undercuts.addWidget(self.undercut_faces)

        self.undercut_table = QTableWidget()
        self.undercut_table.setColumnCount(2)
        self.undercut_table.setHorizontalHeaderLabels(["Check", "Key Value"])
        self.undercut_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_undercuts.addWidget(self.undercut_table)

        layout_undercuts.addStretch()

        idx_undercuts = self.feature_stack.addWidget(self.page_undercuts)
        self.feature_page_indices["undercuts"] = idx_undercuts

    # ------------------------------------------------------------------
    # RIB/BOSS THICKNESS PAGE
    # ------------------------------------------------------------------
        self.page_rib_boss = QWidget()
        layout_rib_boss = QVBoxLayout(self.page_rib_boss)
        layout_rib_boss.setContentsMargins(10, 10, 10, 10)
        layout_rib_boss.setSpacing(6)

        rib_header = QLabel("<b>Rib/Boss Thickness</b>")
        layout_rib_boss.addWidget(rib_header)
        layout_rib_boss.addSpacing(6)

        self.rib_status = QLabel("Rib/Boss: -")
        self.rib_over_thick_vertices = QLabel("Over-thick vertices: -")
        self.rib_factor_label = QLabel("Factor (× wall): -")

        layout_rib_boss.addWidget(self.rib_status)
        layout_rib_boss.addWidget(self.rib_over_thick_vertices)
        layout_rib_boss.addWidget(self.rib_factor_label)

        self.rib_table = QTableWidget()
        self.rib_table.setColumnCount(2)
        self.rib_table.setHorizontalHeaderLabels(["Check", "Key Value"])
        self.rib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout_rib_boss.addWidget(self.rib_table)

        layout_rib_boss.addStretch()

        idx_rib_boss = self.feature_stack.addWidget(self.page_rib_boss)
        self.feature_page_indices["rib_boss"] = idx_rib_boss

    # ------------------------------------------------------------------
    # EXPORT PAGE
    # ------------------------------------------------------------------
        self.page_export = QWidget()
        layout_export = QVBoxLayout(self.page_export)
        layout_export.addWidget(QLabel("Export DFM – feature details will go here."))
        layout_export.addStretch()
        idx_export = self.feature_stack.addWidget(self.page_export)
        self.feature_page_indices["export"] = idx_export

        # Add the stacked widget to the content layout (right side)
        content_layout.addWidget(self.feature_stack, stretch=2)

        # show OPEN page by default
        self.feature_stack.setCurrentIndex(self.feature_page_indices["home"])

        # ---- Menu bar ----
        self._create_menu()

        self.update_axis_legend()

    def update_axis_legend(self):
        """Place X/Y/Z labels near the bottom-left corner of the 3D view."""
        if not hasattr(self, "view"):
            return

        rect = self.view.geometry()
        margin = 24  # pixels from edges

        # bottom-left of GL view in MainWindow coordinates
        x0 = rect.left() + margin
        y0 = rect.bottom() - margin

        # place labels with slight horizontal spacing
        if hasattr(self, "axis_label_x"):
            self.axis_label_x.move(x0, y0)
            self.axis_label_x.raise_()

        if hasattr(self, "axis_label_y"):
            self.axis_label_y.move(x0 + 18, y0)
            self.axis_label_y.raise_()

        if hasattr(self, "axis_label_z"):
            self.axis_label_z.move(x0 + 36, y0)
            self.axis_label_z.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_axis_legend()
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

        export_action = QAction("Export DFM Report...", self)
        export_action.triggered.connect(self.export_dfm_report)
        file_menu.addAction(export_action)

    # ------------------------------------------------------------------
    # Feature tab click handler
    # ------------------------------------------------------------------
    def on_feature_tab_clicked(self, feature_id: str):
        """
        Switch the right-hand panel to the selected feature's page
        and update which DFM issue is highlighted in the 3D view.
        """
        # Switch page
        idx = self.feature_page_indices.get(feature_id)
        if idx is not None:
            self.feature_stack.setCurrentIndex(idx)

        # Decide which DFM issue to highlight
        if feature_id == "thickness":
            self.active_visual_check = "local_thickness"
        elif feature_id == "sharp":
            self.active_visual_check = "sharp_corners"
        elif feature_id == "draft":
            self.active_visual_check = "draft_angle"
        elif feature_id == "undercuts":
            self.active_visual_check = "undercuts"
        elif feature_id == "rib_boss":
            self.active_visual_check = "rib_boss"
        else:
            # home, open, export → no special highlight
            self.active_visual_check = None

        # Re-draw current part with the chosen highlight (if any)
        if self.last_file_path is not None and feature_id != "export":
            self.load_and_display_stl(
                self.last_file_path,
                active_check=self.active_visual_check,
            )
    # ------------------------------------------------------------------
    # File open
    # ------------------------------------------------------------------
    def open_stl_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open STL File",
            "",
            "STL Files (*.stl);;All Files (*.*)"
        )
        if not file_path:
            return

        # Reset active highlight when a new file is opened
        self.active_visual_check = None

        # Always switch back to the OPEN tab when a new file is loaded
        self.feature_buttons["open"].setChecked(True)
        self.feature_stack.setCurrentIndex(self.feature_page_indices["open"])

        # Load STL with no warnings and no colors
        self.load_and_display_stl(
            file_path,
            active_check=self.active_visual_check,
            show_all_warnings=False,
        )

    # ------------------------------------------------------------------
    # Threshold / pull-direction changes
    # ------------------------------------------------------------------
    def on_threshold_changed(self, value):
        if self.last_file_path is None:
            return
        self.load_and_display_stl(
            self.last_file_path,
            active_check=self.active_visual_check,
        )


    # Helper: map UI selection → pull direction vector
    def get_pull_direction_vector(self) -> np.ndarray:
        text = self.combo_pull.currentText()
        if text == "+X":
            return np.array([1.0, 0.0, 0.0], dtype=float)
        elif text == "-X":
            return np.array([-1.0, 0.0, 0.0], dtype=float)
        elif text == "+Y":
            return np.array([0.0, 1.0, 0.0], dtype=float)
        elif text == "-Y":
            return np.array([0.0, -1.0, 0.0], dtype=float)
        elif text == "-Z":
            return np.array([0.0, 0.0, -1.0], dtype=float)
        # default
        return np.array([0.0, 0.0, 1.0], dtype=float)

    # ------------------------------------------------------------------
    # DFM panel update
    # ------------------------------------------------------------------
    def update_dfm_panel(self, dfm_results: dict):
        checks = dfm_results.get("checks", {})
        bbox = dfm_results.get("bbox", {})
        tri_count = dfm_results.get("triangles", "-")

        global_info = checks.get("global_thickness", {})
        local_info = checks.get("local_thickness", {})
        corner_info = checks.get("sharp_corners", {})
        draft_info = checks.get("draft_angle", {})
        und_info = checks.get("undercuts", {})
        rib_boss_info = checks.get("rib_boss", {})

        g_status = global_info.get("status", "-")
        g_smallest = global_info.get("smallest_dimension", "-")

        l_status = local_info.get("status", "-")
        l_min = local_info.get("min_thickness", "-")
        l_count = local_info.get("num_thin_vertices", "-")

        c_status = corner_info.get("status", "-")
        c_num = corner_info.get("num_sharp_edges", "-")

        d_status = draft_info.get("status", "-")
        d_bad_faces = draft_info.get("num_bad_faces", "-")

        u_status = und_info.get("status", "-")
        u_num_faces = und_info.get("num_undercut_faces", "-")

        rb_status = rib_boss_info.get("status", "-")
        rb_num = rib_boss_info.get("num_over_thick_vertices", "-")
        rb_factor = rib_boss_info.get("factor", "-")

        # ---- Home page Part Info ----
        ext = bbox.get("extents")

        if self.last_file_path:
            file_text = f"File: {os.path.basename(self.last_file_path)}"
        else:
            file_text = "File: -"

        tris_text = f"Triangles: {tri_count}"

        if ext is not None and hasattr(ext, "__len__") and len(ext) == 3:
            size_text = (
                f"Size (X×Y×Z): {ext[0]:.2f} × {ext[1]:.2f} × {ext[2]:.2f}"
            )
        else:
            size_text = "Size (X×Y×Z): -"

        # Update Home labels only
        if hasattr(self, "home_file_label"):
            self.home_file_label.setText(file_text)
            self.home_triangles_label.setText(tris_text)
            self.home_size_label.setText(size_text)

        # ---- Home page Part Info (if Home labels exist) ----
        if hasattr(self, "home_file_label"):
            if self.last_file_path:
                self.home_file_label.setText(
                    f"File: {os.path.basename(self.last_file_path)}"
                )
            else:
                self.home_file_label.setText("File: -")

            self.home_triangles_label.setText(f"Triangles: {tri_count}")

            if ext is not None and hasattr(ext, "__len__") and len(ext) == 3:
                self.home_size_label.setText(
                    f"Size (X×Y×Z): {ext[0]:.2f} × {ext[1]:.2f} × {ext[2]:.2f}"
                )
            else:
                self.home_size_label.setText("Size (X×Y×Z): -")
            
        # ---- Update per-feature page labels ----
        # Wall Thickness page
        if hasattr(self, "thickness_status_global"):
            self.thickness_status_global.setText(f"Global Thickness: {g_status}")
        if hasattr(self, "thickness_status_local"):
            self.thickness_status_local.setText(f"Local Thickness: {l_status}")
        if hasattr(self, "thickness_smallest_dim"):
            self.thickness_smallest_dim.setText(f"Smallest Dimension: {g_smallest}")
        if hasattr(self, "thickness_min_local"):
            self.thickness_min_local.setText(f"Min Local Thickness: {l_min}")
        if hasattr(self, "thickness_thin_vertices"):
            self.thickness_thin_vertices.setText(f"Thin Vertices: {l_count}")

        # Sharp Corners page
        if hasattr(self, "sharp_status"):
            self.sharp_status.setText(f"Sharp Corners: {c_status}")
        if hasattr(self, "sharp_edge_count"):
            self.sharp_edge_count.setText(f"Sharp Edges: {c_num}")

        # Draft page
        if hasattr(self, "draft_status"):
            self.draft_status.setText(f"Draft Angle: {d_status}")
        if hasattr(self, "draft_bad_faces"):
            self.draft_bad_faces.setText(f"Faces below min draft: {d_bad_faces}")

        # Undercuts page
        if hasattr(self, "undercut_status"):
            self.undercut_status.setText(f"Undercuts: {u_status}")
        if hasattr(self, "undercut_faces"):
            self.undercut_faces.setText(f"Undercut Faces: {u_num_faces}")

        # Rib/Boss page
        if hasattr(self, "rib_status"):
            self.rib_status.setText(f"Rib/Boss: {rb_status}")
        if hasattr(self, "rib_over_thick_vertices"):
            self.rib_over_thick_vertices.setText(
                f"Over-thick vertices: {rb_num}"
            )
        if hasattr(self, "rib_factor_label"):
            self.rib_factor_label.setText(f"Factor (× wall): {rb_factor}")
       
        # ---- Per-feature detail tables ----
        def add_row(table: QTableWidget, name, value):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(name)))
            table.setItem(row, 1, QTableWidgetItem(str(value)))

        # Wall Thickness details
        if hasattr(self, "thickness_table"):
            self.thickness_table.setRowCount(0)
            add_row(self.thickness_table, "Global thickness – smallest dim", g_smallest)
            add_row(self.thickness_table, "Local thickness – min local", l_min)
            add_row(self.thickness_table, "Thin vertices", l_count)

        # Sharp Corners details
        if hasattr(self, "sharp_table"):
            self.sharp_table.setRowCount(0)
            add_row(self.sharp_table, "Sharp corners – edge count", c_num)
            add_row(
                self.sharp_table,
                "Angle threshold (deg)",
                corner_info.get("angle_threshold_deg", "-"),
            )
            add_row(
                self.sharp_table,
                "Max sharp angle (deg)",
                corner_info.get("max_sharp_angle_deg", "-"),
            )

        # Draft details
        if hasattr(self, "draft_table"):
            self.draft_table.setRowCount(0)
            add_row(self.draft_table, "Faces below min draft", d_bad_faces)
            add_row(
                self.draft_table,
                "Min draft angle (deg)",
                draft_info.get("min_draft_angle", "-"),
            )
            add_row(
                self.draft_table,
                "Draft threshold (deg)",
                draft_info.get("angle_threshold_deg", "-"),
            )
            add_row(
                self.draft_table,
                "Pull direction",
                self.combo_pull.currentText(),
            )

        # Undercuts details
        if hasattr(self, "undercut_table"):
            self.undercut_table.setRowCount(0)
            add_row(self.undercut_table, "Undercut faces", u_num_faces)
            add_row(
                self.undercut_table,
                "Angle threshold (deg)",
                und_info.get("angle_threshold_deg", "-"),
            )
            add_row(
                self.undercut_table,
                "Max undercut angle (deg)",
                und_info.get("max_undercut_angle_deg", "-"),
            )

        # Rib/Boss details
        if hasattr(self, "rib_table"):
            self.rib_table.setRowCount(0)
            add_row(
                self.rib_table,
                "Nominal wall thickness",
                rib_boss_info.get("base_wall_thickness", "-"),
            )
            add_row(
                self.rib_table,
                "Max thickness",
                rib_boss_info.get("max_thickness", "-"),
            )
            add_row(self.rib_table, "Factor (× wall)", rb_factor)
            add_row(
                self.rib_table,
                "Threshold thickness",
                rib_boss_info.get("threshold", "-"),
            )
            add_row(
                self.rib_table,
                "Over-thick vertices",
                rb_num,
            )
    # ------------------------------------------------------------------
    # Export DFM report
    # ------------------------------------------------------------------
    def export_dfm_report(self):
        if self.last_dfm_results is None:
            QMessageBox.information(
                self,
                "No Analysis",
                "Please load an STL and run DFM analysis before exporting a report.",
            )
            return

        base_name = "model"
        if self.last_file_path:
            base_name = os.path.splitext(os.path.basename(self.last_file_path))[0]

        default_name = f"{base_name}_dfm_report.txt"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save DFM Report",
            default_name,
            "Text Files (*.txt);;All Files (*.*)"
        )

        if not save_path:
            return

        report_dir = os.path.dirname(save_path)
        report_base = os.path.splitext(os.path.basename(save_path))[0]
        screenshot_path = os.path.join(report_dir, f"{report_base}_screenshot.png")

        # Screenshot
        try:
            pixmap = self.grab()
            pixmap.save(screenshot_path)
            screenshot_note = f"Screenshot saved to: {screenshot_path}"
        except Exception as e:
            screenshot_note = f"Screenshot capture failed: {e}"

        dfm = self.last_dfm_results
        checks = dfm.get("checks", {})
        bbox = dfm.get("bbox", {})
        tri_count = dfm.get("triangles", "N/A")

        global_info = checks.get("global_thickness", {})
        local_info = checks.get("local_thickness", {})
        corner_info = checks.get("sharp_corners", {})
        draft_info = checks.get("draft_angle", {})
        und_info = checks.get("undercuts", {})
        rib_boss_info = checks.get("rib_boss", {})

        lines = []
        lines.append("SmartDFM – Injection Molding DFM Report")
        lines.append("=" * 50)
        lines.append("")
        if self.last_file_path:
            lines.append(f"File: {self.last_file_path}")
        lines.append(f"Triangles: {tri_count}")
        lines.append("")

        # Thresholds
        lines.append("Thresholds Used")
        lines.append("-" * 30)
        lines.append(f"  Global min thickness: {self.spin_global.value()}")
        lines.append(f"  Local wall thickness: {self.spin_local.value()}")
        lines.append("")

        # Pull direction
        lines.append("Draft / Pull Direction")
        lines.append("-" * 30)
        lines.append(f"  Pull direction: {self.combo_pull.currentText()}")
        lines.append("")

        # Bounding box
        min_b = bbox.get("min")
        max_b = bbox.get("max")
        ext = bbox.get("extents")
        if min_b is not None and max_b is not None and ext is not None:
            lines.append("Bounding Box (model units):")
            lines.append(f"  Min: {min_b}")
            lines.append(f"  Max: {max_b}")
            lines.append(f"  Extents: {ext}")
            lines.append("")

        # Global thickness
        lines.append("Global Thickness Check")
        lines.append("-" * 30)
        lines.append(f"  Status: {global_info.get('status', 'N/A')}")
        lines.append(f"  Message: {global_info.get('message', '')}")
        lines.append(f"  Smallest Dimension: {global_info.get('smallest_dimension', 'N/A')}")
        lines.append(f"  Min Allowed: {global_info.get('min_allowed', 'N/A')}")
        lines.append("")

        # Local thickness
        lines.append("Local Wall Thickness Check")
        lines.append("-" * 30)
        lines.append(f"  Status: {local_info.get('status', 'N/A')}")
        lines.append(f"  Message: {local_info.get('message', '')}")
        lines.append(f"  Min Thickness (approx): {local_info.get('min_thickness', 'N/A')}")
        lines.append(f"  Thin Vertices: {local_info.get('num_thin_vertices', 'N/A')}")
        lines.append(f"  Threshold: {local_info.get('threshold', 'N/A')}")
        lines.append("")

        # Sharp corners
        lines.append("Sharp Corner Check (dihedral-angle based)")
        lines.append("-" * 30)
        lines.append(f"  Status: {corner_info.get('status', 'N/A')}")
        lines.append(f"  Message: {corner_info.get('message', '')}")
        lines.append(f"  Sharp Edges: {corner_info.get('num_sharp_edges', 'N/A')}")
        lines.append(f"  Angle Threshold (deg): {corner_info.get('angle_threshold_deg', 'N/A')}")
        lines.append(f"  Max Sharp Angle (deg): {corner_info.get('max_sharp_angle_deg', 'N/A')}")
        lines.append("")

        # Draft angle
        lines.append("Draft Angle Check")
        lines.append("-" * 30)
        lines.append(f"  Status: {draft_info.get('status', 'N/A')}")
        lines.append(f"  Message: {draft_info.get('message', '')}")
        lines.append(f"  Min Draft Angle (deg): {draft_info.get('min_draft_angle', 'N/A')}")
        lines.append(f"  Faces below min draft: {draft_info.get('num_bad_faces', 'N/A')}")
        lines.append(f"  Draft Threshold (deg): {draft_info.get('angle_threshold_deg', 'N/A')}")
        lines.append("")

        # Undercut check
        lines.append("Undercut Check")
        lines.append("-" * 30)
        lines.append(f"  Status: {und_info.get('status', 'N/A')}")
        lines.append(f"  Message: {und_info.get('message', '')}")
        lines.append(f"  Undercut faces: {und_info.get('num_undercut_faces', 'N/A')}")
        lines.append(f"  Angle Threshold (deg): {und_info.get('angle_threshold_deg', 'N/A')}")
        lines.append(f"  Max Undercut Angle (deg): {und_info.get('max_undercut_angle_deg', 'N/A')}")
        lines.append("")

        # Rib / Boss thickness check
        lines.append("Rib/Boss Thickness Check")
        lines.append("-" * 30)
        lines.append(f"  Status: {rib_boss_info.get('status', 'N/A')}")
        lines.append(f"  Message: {rib_boss_info.get('message', '')}")
        lines.append(f"  Nominal wall thickness: {rib_boss_info.get('base_wall_thickness', 'N/A')}")
        lines.append(f"  Max thickness: {rib_boss_info.get('max_thickness', 'N/A')}")
        lines.append(f"  Factor (× wall): {rib_boss_info.get('factor', 'N/A')}")
        lines.append(f"  Threshold thickness: {rib_boss_info.get('threshold', 'N/A')}")
        lines.append(f"  Over-thick vertices: {rib_boss_info.get('num_over_thick_vertices', 'N/A')}")
        lines.append("")

        # Screenshot info
        lines.append("Screenshot")
        lines.append("-" * 30)
        lines.append(f"  {screenshot_note}")
        lines.append("")

        # Summary
        summary = dfm.get("summary", "")
        if summary:
            lines.append("Summary")
            lines.append("-" * 30)
            lines.append(f"  {summary}")
            lines.append("")

        try:
            with open(save_path, "w") as f:
                f.write("\n".join(lines))
            QMessageBox.information(
                self,
                "Report Saved",
                f"DFM report and screenshot saved.\n\nReport: {save_path}\nScreenshot: {screenshot_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving Report",
                f"Could not save report:\n\n{e}",
            )

    # ------------------------------------------------------------------
    # Load, DFM, and display
    # ------------------------------------------------------------------
    def load_and_display_stl(
        self,
        file_path: str,
        active_check: str | None = None,
        show_all_warnings: bool = False,
    ):
        """
        Load STL, run DFM checks, and display mesh.
        Thin regions (by local wall thickness) are colored red.
        Sharp corners are colored blue.
        Bad draft angle (insufficient draft) are colored green.
        Undercuts are yellow.
        Rib/Boss over-thickness is orange.
        """
        try:
            vertices, faces = load_stl(file_path)

            if vertices.size == 0 or faces.size == 0:
                raise ValueError("STL file contains no geometry.")

            tri_count = faces.shape[0]
            min_bounds = vertices.min(axis=0)
            max_bounds = vertices.max(axis=0)
            extents = max_bounds - min_bounds

            # Read thresholds from UI
            min_global = self.spin_global.value()
            min_local = self.spin_local.value()
            pull_dir = self.get_pull_direction_vector()

            # Run DFM pipeline
            dfm_results = run_all_checks(
                vertices,
                faces,
                min_global_thickness=min_global,
                min_local_thickness=min_local,
                pull_direction=pull_dir,
            )
            dfm_summary = dfm_results.get("summary", "DFM: no summary")
            checks = dfm_results.get("checks", {})

            # Store for export / rerun
            self.last_dfm_results = dfm_results
            self.last_file_path = file_path

            # Update DFM panel
            self.update_dfm_panel(dfm_results)

            local_chk = checks.get("local_thickness", {})
            global_chk = checks.get("global_thickness", {})
            corner_chk = checks.get("sharp_corners", {})
            draft_chk = checks.get("draft_angle", {})
            undercut_chk = checks.get("undercuts", {})
            rib_boss_chk = checks.get("rib_boss", {})

            per_vertex_thickness = local_chk.get("per_vertex_thickness", None)
            threshold = local_chk.get("threshold", None)
            corner_mask = corner_chk.get("corner_vertex_mask", None)
            draft_vertex_mask = draft_chk.get("bad_vertex_mask", None)
            undercut_vertex_mask = undercut_chk.get("bad_vertex_mask", None)
            rib_boss_vertex_mask = rib_boss_chk.get("bad_vertex_mask", None)

            # Center + normalize
            center = vertices.mean(axis=0)
            vertices_centered = vertices - center

            max_extent = np.abs(vertices_centered).max()
            if max_extent > 0:
                vertices_centered = vertices_centered / max_extent * 10.0
            
            # Compute bounding box in centered coordinates
            min_c = vertices_centered.min(axis=0)
            max_c = vertices_centered.max(axis=0)
            extent_c = max_c - min_c
            max_extent_c = float(np.max(extent_c)) if np.any(extent_c) else 10.0

            # Position the axis slightly outside the model (e.g., near one corner)
            if hasattr(self, "axis_item"):
                # Size the axis at ~20% of model size
                axis_size = max_extent_c * 0.2 if max_extent_c > 0 else 5.0
                self.axis_item.setSize(x=axis_size, y=axis_size, z=axis_size)

                # Place it a bit “below/left/front” of the bounding box
                offset = 0.1 * extent_c  # small margin
                axis_pos = min_c - offset

                # IMPORTANT: GLAxisItem has no setPos -> use transforms
                self.axis_item.resetTransform()
                self.axis_item.translate(axis_pos[0], axis_pos[1], axis_pos[2])

            
            # Build mesh geometry once, for normals + rendering
            mesh_geom = gl.MeshData(
                vertexes=vertices_centered,
                faces=faces,
            )

            # Per-vertex normals for simple lighting
            normals = mesh_geom.vertexNormals()  # shape: (N, 3)
            
            # Build per-vertex colors
            vertex_colors = np.zeros((vertices.shape[0], 4), dtype=float)
            vertex_colors[:, :] = [0.7, 0.7, 0.7, 1.0]  # grey default

            # --- Build Boolean masks ---

            # Thin regions (local thickness)
            thin_mask = np.zeros(vertices.shape[0], dtype=bool)
            if per_vertex_thickness is not None and threshold is not None:
                t = np.array(per_vertex_thickness, dtype=float)
                finite = np.isfinite(t)
                if t.shape[0] == vertices.shape[0]:
                    thin_mask = finite & (t < threshold)

            # Sharp corners
            corner_vertex_mask = np.zeros(vertices.shape[0], dtype=bool)
            if corner_mask is not None:
                cm = np.array(corner_mask, dtype=bool)
                if cm.shape[0] == vertices.shape[0]:
                    corner_vertex_mask = cm

            # Draft issues
            draft_bad_mask = np.zeros(vertices.shape[0], dtype=bool)
            if draft_vertex_mask is not None:
                dm = np.array(draft_vertex_mask, dtype=bool)
                if dm.shape[0] == vertices.shape[0]:
                    draft_bad_mask = dm

            # Undercuts
            undercut_bad_mask = np.zeros(vertices.shape[0], dtype=bool)
            if undercut_vertex_mask is not None:
                um = np.array(undercut_vertex_mask, dtype=bool)
                if um.shape[0] == vertices.shape[0]:
                    undercut_bad_mask = um

            # Rib/Boss over-thickness
            rib_bad_mask = np.zeros(vertices.shape[0], dtype=bool)
            if rib_boss_vertex_mask is not None:
                rb = np.array(rib_boss_vertex_mask, dtype=bool)
                if rb.shape[0] == vertices.shape[0]:
                    rib_bad_mask = rb
            
            # --- Simple directional lighting (Blender-like feel) ---
            # Light coming from above/side in view space
            light_dir = np.array([0.3, 0.5, 0.8], dtype=float)
            light_dir /= np.linalg.norm(light_dir)

            # Ensure normals is proper shape
            if normals is not None and normals.shape[0] == vertex_colors.shape[0]:
                # cosine of angle between normal and light
                dots = np.einsum("ij,j->i", normals, light_dir)
                dots = np.clip(dots, 0.0, 1.0)

                # map to brightness range (ambient + diffuse)
                # 0.35 ambient, up to ~1.0 at best alignment
                intensity = 0.35 + 0.65 * dots

                # apply to RGB channels only, keep alpha = 1
                vertex_colors[:, 0:3] *= intensity[:, None]


            # --- Apply checkbox filters ---
            # --- Apply active_check filter ---
            # Show only the issue associated with active_check.
            # If active_check is None, show no special highlights (all grey).
            if active_check is None:
                thin_mask[:] = False
                corner_vertex_mask[:] = False
                draft_bad_mask[:] = False
                undercut_bad_mask[:] = False
                rib_bad_mask[:] = False
            else:
                if active_check != "local_thickness":
                    thin_mask[:] = False
                if active_check != "sharp_corners":
                    corner_vertex_mask[:] = False
                if active_check != "draft_angle":
                    draft_bad_mask[:] = False
                if active_check != "undercuts":
                    undercut_bad_mask[:] = False
                if active_check != "rib_boss":
                    rib_bad_mask[:] = False

            # --- Assign colors: GOOD = green, BAD = red for active feature ---
            # Start with neutral grey
            vertex_colors = np.zeros((vertices.shape[0], 4), dtype=float)
            vertex_colors[:, :] = [0.7, 0.7, 0.7, 1.0]

            if active_check is not None:
                # Choose the "bad" mask based on the active feature
                if active_check == "local_thickness":
                    bad_mask = thin_mask
                elif active_check == "sharp_corners":
                    bad_mask = corner_vertex_mask
                elif active_check == "draft_angle":
                    bad_mask = draft_bad_mask
                elif active_check == "undercuts":
                    bad_mask = undercut_bad_mask
                elif active_check == "rib_boss":
                    bad_mask = rib_bad_mask
                else:
                    bad_mask = np.zeros(vertices.shape[0], dtype=bool)

                ok_mask = ~bad_mask

                # Non-defect regions = green
                vertex_colors[ok_mask] = [0.0, 0.9, 0.0, 1.0]   # green
                # Defect regions = red
                vertex_colors[bad_mask] = [1.0, 0.0, 0.0, 0.9]  # red
            # else: active_check is None → leave everything grey

            # Attach shaded colors to the mesh geometry
            mesh_geom.setVertexColors(vertex_colors)

            if self.mesh_item is not None:
                self.view.removeItem(self.mesh_item)

            self.mesh_item = gl.GLMeshItem(
                meshdata=mesh_geom,
                smooth=True,                 # smooth shading like CAD
                drawFaces=True,
                drawEdges=True,
                edgeColor=(0.2, 0.2, 0.2, 1.0),
            )
            self.view.addItem(self.mesh_item)

            def _maybe_warn(check_key: str, title: str, message: str):
                # If popups suppressed entirely (file open or uncheck):
                if active_check is None:
                    return
                if active_check != check_key:
                    return
                QMessageBox.warning(self, title, message)

            # Warnings
            if global_chk and global_chk.get("status") == "WARNING":
                _maybe_warn(
                    "global_thickness",
                    "DFM Warning – Global Thickness",
                    global_chk.get("message", "")
                )

            if local_chk and local_chk.get("status") == "WARNING":
                _maybe_warn(
                    "local_thickness",
                    "DFM Warning – Local Wall Thickness",
                    local_chk.get("message", "")
                )

            if corner_chk and corner_chk.get("status") == "WARNING":
                _maybe_warn(
                    "sharp_corners",
                    "DFM Warning – Sharp Corners",
                    corner_chk.get("message", "")
                )

            if draft_chk and draft_chk.get("status") == "WARNING":
                _maybe_warn(
                    "draft_angle",
                    "DFM Warning – Draft Angle",
                    draft_chk.get("message", "")
                )

            if undercut_chk and undercut_chk.get("status") == "WARNING":
                _maybe_warn(
                    "undercuts",
                    "DFM Warning – Undercuts",
                    undercut_chk.get("message", "")
                )

            if rib_boss_chk and rib_boss_chk.get("status") == "WARNING":
                _maybe_warn(
                    "rib_boss",
                    "DFM Warning – Rib/Boss Thickness",
                    rib_boss_chk.get("message", "Over-thick rib/boss regions detected."),
                )

            # Status bar
            if hasattr(self, "status"):
                msg = (
                    f"Loaded: {os.path.basename(file_path)}  |  "
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