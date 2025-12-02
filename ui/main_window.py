# ui/main_window.py

from email.mime import message
import sys
import os
import numpy as np

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMenuBar,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QPushButton, QDoubleSpinBox, QComboBox, QCheckBox
)
from PySide6.QtGui import QAction

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
        self.resize(1200, 400)

        # ---- Status bar ----
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # Store last analysis and file path (for export + re-run)
        self.last_dfm_results = None
        self.last_file_path = None

        # ---- Central widget ----
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Root vertical layout (button bar on top, content below)
        root_layout = QVBoxLayout(central_widget)

        # ---- Top button bar ----
        button_bar = QHBoxLayout()

        # Open STL button
        self.open_button = QPushButton("Open STL…")
        self.open_button.clicked.connect(self.open_stl_dialog)
        button_bar.addWidget(self.open_button)

        # Export DFM Report button
        self.export_button = QPushButton("Export DFM Report…")
        self.export_button.clicked.connect(self.export_dfm_report)
        button_bar.addWidget(self.export_button)

        button_bar.addStretch()
        root_layout.addLayout(button_bar)

        # ---- Content layout: 3D view (left) + DFM panel (right) ----
        content_layout = QHBoxLayout()
        root_layout.addLayout(content_layout)

        # ---- 3D View ----
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor((0.9, 0.9, 0.9, 1.0))
        self.view.opts["distance"] = 40
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

        # --- SECTION 0: Title ---
        self.lbl_title = QLabel("<b>Injection Molding DFM Summary</b>")
        dfm_layout.addWidget(self.lbl_title)

        dfm_layout.addSpacing(6)

        # --- SECTION 1: Part Info ---
        self.lbl_part_header = QLabel("<b>Part Info</b>")
        dfm_layout.addWidget(self.lbl_part_header)

        self.lbl_part_name = QLabel("File: -")
        self.lbl_part_tris = QLabel("Triangles: -")
        self.lbl_part_size = QLabel("Size (X×Y×Z): -")

        dfm_layout.addWidget(self.lbl_part_name)
        dfm_layout.addWidget(self.lbl_part_tris)
        dfm_layout.addWidget(self.lbl_part_size)

        dfm_layout.addSpacing(10)

        # --- SECTION 2: Process Settings (thickness + pull direction) ---
        self.lbl_thresholds = QLabel("<b>Process Settings</b>")
        dfm_layout.addWidget(self.lbl_thresholds)

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
        dfm_layout.addLayout(global_row)

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
        dfm_layout.addLayout(local_row)

        # Pull direction selector
        pull_row = QHBoxLayout()
        pull_row.addWidget(QLabel("Pull direction:"))
        self.combo_pull = QComboBox()
        self.combo_pull.addItems(["+Z", "-Z", "+X", "-X", "+Y", "-Y"])
        self.combo_pull.setCurrentText("+Z")
        self.combo_pull.currentIndexChanged.connect(self.on_threshold_changed)
        pull_row.addWidget(self.combo_pull)
        dfm_layout.addLayout(pull_row)

        dfm_layout.addSpacing(10)

        # --- SECTION 3: DFM Overview (traffic-light style) ---
        self.lbl_overview = QLabel("<b>DFM Overview</b>")
        dfm_layout.addWidget(self.lbl_overview)

        self.lbl_global_status = QLabel("Global Thickness: -")
        self.lbl_local_status = QLabel("Local Thickness: -")
        self.lbl_corner_status = QLabel("Sharp Corners: -")
        self.lbl_draft_status = QLabel("Draft Angle: -")
        self.lbl_undercut_status = QLabel("Undercuts: -")

        dfm_layout.addWidget(self.lbl_global_status)
        dfm_layout.addWidget(self.lbl_local_status)
        dfm_layout.addWidget(self.lbl_corner_status)
        dfm_layout.addWidget(self.lbl_draft_status)
        dfm_layout.addWidget(self.lbl_undercut_status)

        dfm_layout.addSpacing(8)

        # Detailed summary for thickness / draft
        self.lbl_global_value = QLabel("Smallest Dimension: -")
        self.lbl_local_min = QLabel("Min Local Thickness: -")
        self.lbl_local_thin_count = QLabel("Thin Vertices: -")
        self.lbl_corner_count = QLabel("Sharp Edges: -")
        self.lbl_draft_bad_faces = QLabel("Faces below min draft: -")
        self.lbl_undercut_faces = QLabel("Undercut Faces: -")

        dfm_layout.addWidget(self.lbl_global_value)
        dfm_layout.addWidget(self.lbl_local_min)
        dfm_layout.addWidget(self.lbl_local_thin_count)
        dfm_layout.addWidget(self.lbl_corner_count)
        dfm_layout.addWidget(self.lbl_draft_bad_faces)
        dfm_layout.addWidget(self.lbl_undercut_faces)

        dfm_layout.addSpacing(10)

        # --- SECTION 4: Color Legend ---
        self.lbl_legend_header = QLabel("<b>Color Legend</b>")
        dfm_layout.addWidget(self.lbl_legend_header)

        def make_color_row(color_css: str, text: str):
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setStyleSheet(
                f"background-color: {color_css}; border: 1px solid #333;"
            )
            swatch.setFixedSize(16, 16)  # fixed square, won't resize
            row.addWidget(swatch)
            row.addSpacing(6)
            row.addWidget(QLabel(text))
            row.addStretch()
            return row

        dfm_layout.addLayout(
            make_color_row("red", "Thin regions (local thickness below threshold)")
        )
        dfm_layout.addLayout(
            make_color_row("lime", "Faces with insufficient draft")
        )
        dfm_layout.addLayout(
            make_color_row("blue", "Sharp internal corners / edges")
        )
        dfm_layout.addLayout(
            make_color_row("yellow", "Undercuts / back-draft faces")
        )
        dfm_layout.addLayout(
        make_color_row("orange", "Rib/Boss over-thickness regions")
)

        dfm_layout.addSpacing(10)

        # --- SECTION 5: Issue visibility toggles ---
        self.lbl_filters_header = QLabel("<b>Show in 3D view</b>")
        dfm_layout.addWidget(self.lbl_filters_header)

        self.chk_show_thickness = QCheckBox("Thin regions")
        self.chk_show_thickness.setChecked(False)
        self.chk_show_draft = QCheckBox("Draft issues")
        self.chk_show_draft.setChecked(False)
        self.chk_show_corners = QCheckBox("Sharp corners")
        self.chk_show_corners.setChecked(False)
        self.chk_show_undercuts = QCheckBox("Undercuts")
        self.chk_show_undercuts.setChecked(False)
        self.chk_show_rib_boss = QCheckBox("Rib/Boss thickness")
        self.chk_show_rib_boss.setChecked(False)

        # When any checkbox changes, just re-run coloring on the current part
        self.chk_show_thickness.stateChanged.connect(self.on_issue_filter_changed)
        self.chk_show_draft.stateChanged.connect(self.on_issue_filter_changed)
        self.chk_show_corners.stateChanged.connect(self.on_issue_filter_changed)
        self.chk_show_undercuts.stateChanged.connect(self.on_issue_filter_changed)
        self.chk_show_rib_boss.stateChanged.connect(self.on_issue_filter_changed)

        dfm_layout.addWidget(self.chk_show_thickness)
        dfm_layout.addWidget(self.chk_show_draft)
        dfm_layout.addWidget(self.chk_show_corners)
        dfm_layout.addWidget(self.chk_show_undercuts)
        dfm_layout.addWidget(self.chk_show_rib_boss)
        dfm_layout.addSpacing(10)

        # --- SECTION 6: Details Table (compact) ---
        details_label = QLabel("<b>Details</b>")
        dfm_layout.addWidget(details_label)

        self.dfm_table = QTableWidget()
        self.dfm_table.setColumnCount(2)
        self.dfm_table.setHorizontalHeaderLabels(["Check", "Key Value"])
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

        export_action = QAction("Export DFM Report...", self)
        export_action.triggered.connect(self.export_dfm_report)
        file_menu.addAction(export_action)

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
        # Reset all issue filters when a new file is opened
        self.chk_show_thickness.setChecked(False)
        self.chk_show_draft.setChecked(False)
        self.chk_show_corners.setChecked(False)
        self.chk_show_undercuts.setChecked(False)
        self.chk_show_rib_boss.setChecked(False)

        # Load STL with no warnings and no colors
        self.load_and_display_stl(
            file_path,
            active_check=None,
            show_all_warnings=False,
        )

    # ------------------------------------------------------------------
    # Threshold / pull-direction changes
    # ------------------------------------------------------------------
    def on_threshold_changed(self, value):
        if self.last_file_path is None:
            return
        self.load_and_display_stl(self.last_file_path)
    
    def on_issue_filter_changed(self, state):
        """
        Handles toggling of visibility checkboxes.
        OFF → ON: show popup for this check ONLY
        ON → OFF: no popup
        """
        if self.last_file_path is None or self.last_dfm_results is None:
            return

        sender = self.sender()

        # Detect which checkbox was toggled
        if sender is self.chk_show_thickness:
            check_key = "local_thickness"
            now_enabled = self.chk_show_thickness.isChecked()

        elif sender is self.chk_show_draft:
            check_key = "draft_angle"
            now_enabled = self.chk_show_draft.isChecked()

        elif sender is self.chk_show_corners:
            check_key = "sharp_corners"
            now_enabled = self.chk_show_corners.isChecked()

        elif sender is self.chk_show_undercuts:
            check_key = "undercuts"
            now_enabled = self.chk_show_undercuts.isChecked()

        elif sender is self.chk_show_rib_boss:
            check_key = "rib_boss"
            now_enabled = self.chk_show_rib_boss.isChecked()
        else:
            return

        # OFF → ON → show popup for this check only
        # OFF → ON → show popup
        # ON → OFF → no popup
        if now_enabled:
            self.load_and_display_stl(
                self.last_file_path,
                active_check=check_key,
                show_all_warnings=False,
            )
        else:
            # Recolor and refresh WITHOUT any popup
            self.load_and_display_stl(
                self.last_file_path,
                active_check=None,
                show_all_warnings=False,
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
        # ---- Part Info Labels ----
        if self.last_file_path:
            self.lbl_part_name.setText(f"File: {os.path.basename(self.last_file_path)}")
        else:
            self.lbl_part_name.setText("File: -")

        self.lbl_part_tris.setText(f"Triangles: {tri_count}")

        ext = bbox.get("extents")
        if ext is not None and hasattr(ext, "__len__") and len(ext) == 3:
            self.lbl_part_size.setText(
                f"Size (X×Y×Z): {ext[0]:.2f} × {ext[1]:.2f} × {ext[2]:.2f}"
            )
        else:
            self.lbl_part_size.setText("Size (X×Y×Z): -")

        # ---- Overview Labels ----
        self.lbl_global_status.setText(f"Global Thickness: {g_status}")
        self.lbl_local_status.setText(f"Local Thickness: {l_status}")
        self.lbl_corner_status.setText(f"Sharp Corners: {c_status}")
        self.lbl_draft_status.setText(f"Draft Angle: {d_status}")
        self.lbl_undercut_status.setText(f"Undercuts: {u_status}")

        self.lbl_global_value.setText(f"Smallest Dimension: {g_smallest}")
        self.lbl_local_min.setText(f"Min Local Thickness: {l_min}")
        self.lbl_local_thin_count.setText(f"Thin Vertices: {l_count}")
        self.lbl_corner_count.setText(f"Sharp Edges: {c_num}")
        self.lbl_draft_bad_faces.setText(f"Faces below min draft: {d_bad_faces}")
        self.lbl_undercut_faces.setText(f"Undercut Faces: {u_num_faces}")

        # ---- Details Table (compact) ----
        self.dfm_table.setRowCount(0)

        def add_row(name, value):
            row = self.dfm_table.rowCount()
            self.dfm_table.insertRow(row)
            self.dfm_table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.dfm_table.setItem(row, 1, QTableWidgetItem(str(value)))

        add_row("Global thickness – smallest dim", g_smallest)
        add_row("Local thickness – min local", l_min)
        add_row("Sharp corners – edge count", c_num)
        add_row("Draft – faces below min", d_bad_faces)
        add_row("Pull direction", self.combo_pull.currentText())
        add_row("Undercuts - Faces count", u_num_faces)
        add_row("Rib/Boss - Over-thick vertices", rb_num)
        add_row("Rib/Boss - Factor", rb_factor)


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
            def _maybe_warn(check_key: str, title: str, message: str):
            # If this is a checkbox-triggered refresh,
            # show popup ONLY for the check that was toggled.
                if not show_all_warnings:
                    if active_check != check_key:
                        return
                QMessageBox.warning(self, title, message)

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

            # --- Apply checkbox filters ---
            if not self.chk_show_thickness.isChecked():
                thin_mask[:] = False
            if not self.chk_show_draft.isChecked():
                draft_bad_mask[:] = False
            if not self.chk_show_corners.isChecked():
                corner_vertex_mask[:] = False
            if not self.chk_show_undercuts.isChecked():
                undercut_bad_mask[:] = False
            if not self.chk_show_rib_boss.isChecked():
                rib_bad_mask[:] = False

            # --- Assign colors with priority ---
            # Priority:
            #   1) Undercuts – yellow
            #   2) Thin regions – red
            #   3) Rib/Boss over-thick – orange
            #   4) Draft issues – green
            #   5) Sharp corners – blue

            # 1) Undercuts: yellow
            vertex_colors[undercut_bad_mask] = [1.0, 1.0, 0.0, 1.0]  # yellow

            # 2) Thin regions: red (not undercut)
            thin_only = thin_mask & (~undercut_bad_mask)
            vertex_colors[thin_only] = [1.0, 0.0, 0.0, 1.0]  # red

            # 3) Rib/Boss over-thickness: orange (not undercut, not thin)
            rib_only = rib_bad_mask & (~undercut_bad_mask) & (~thin_mask)
            vertex_colors[rib_only] = [1.0, 0.5, 0.0, 1.0]  # orange

            # 4) Draft issues: green (not undercut, not thin, not rib)
            draft_only = (
                draft_bad_mask
                & (~undercut_bad_mask)
                & (~thin_mask)
                & (~rib_bad_mask)
            )
            vertex_colors[draft_only] = [0.0, 1.0, 0.0, 1.0]  # green

            # 5) Sharp corners: blue (only where nothing else applied)
            corner_only = (
                corner_vertex_mask
                & (~thin_mask)
                & (~draft_bad_mask)
                & (~undercut_bad_mask)
                & (~rib_bad_mask)
            )
            vertex_colors[corner_only] = [0.0, 0.0, 1.0, 1.0]  # blue

            mesh_data = gl.MeshData(
                vertexes=vertices_centered,
                faces=faces,
                vertexColors=vertex_colors,
            )

            if self.mesh_item is not None:
                self.view.removeItem(self.mesh_item)

            self.mesh_item = gl.GLMeshItem(
                meshdata=mesh_data,
                smooth=False,
                drawFaces=True,
                drawEdges=True,
                edgeColor=(0, 0, 0, 1.0),
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
            # Global thickness
            # GLOBAL thickness
            if global_chk and global_chk.get("status") == "WARNING":
                _maybe_warn(
                    "global_thickness",
                    "DFM Warning – Global Thickness",
                    global_chk.get("message", "")
                )

            # LOCAL thickness
            if local_chk and local_chk.get("status") == "WARNING":
                _maybe_warn(
                    "local_thickness",
                    "DFM Warning – Local Wall Thickness",
                    local_chk.get("message", "")
                )

            # SHARP corners
            if corner_chk and corner_chk.get("status") == "WARNING":
                _maybe_warn(
                    "sharp_corners",
                    "DFM Warning – Sharp Corners",
                    corner_chk.get("message", "")
                )

            # DRAFT angle
            if draft_chk and draft_chk.get("status") == "WARNING":
                _maybe_warn(
                    "draft_angle",
                    "DFM Warning – Draft Angle",
                    draft_chk.get("message", "")
                )

            # UNDERCUTS
            if undercut_chk and undercut_chk.get("status") == "WARNING":
                _maybe_warn(
                    "undercuts",
                    "DFM Warning – Undercuts",
                    undercut_chk.get("message", "")
                )
            # RIB/BOSS thickness
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