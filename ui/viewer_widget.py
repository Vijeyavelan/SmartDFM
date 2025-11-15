"""Embedded PyVista viewer widget using pyvistaqt.QtInteractor."""

from typing import Optional

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PyQt6 import QtWidgets


class ViewerWidget(QtWidgets.QFrame):
    """A reusable widget that hosts a PyVista QtInteractor."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setFrameStyle(QtWidgets.QFrame.Shape.StyledPanel | QtWidgets.QFrame.Shadow.Raised)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # PyVista Qt interactor
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter)

        # Small default scene
        self.plotter.add_text("SmartDFM Viewer", font_size=10)
        self.plotter.show_bounds(grid="front")
        self.plotter.reset_camera()

    def clear(self) -> None:
        """Clear the scene."""
        self.plotter.clear()

    def set_pv_mesh(
        self,
        pv_mesh: pv.PolyData,
        scalars: Optional[np.ndarray] = None,
        scalar_bar_title: Optional[str] = None,
        show_edges: bool = True,
    ) -> None:
        """Display a PyVista mesh inside the embedded viewer.

        Parameters
        ----------
        pv_mesh : pv.PolyData
            The mesh to display.
        scalars : array-like, optional
            Per-cell or per-point scalars for color mapping.
        scalar_bar_title : str, optional
            Label for the scalar bar.
        show_edges : bool
            Whether to draw mesh edges.
        """
        self.plotter.clear()

        mesh = pv_mesh.copy()
        if scalars is not None:
            name = scalar_bar_title or "scalars"
            # Try to guess if scalars are cell or point data
            if len(scalars) == mesh.n_cells:
                mesh.cell_data[name] = scalars
            elif len(scalars) == mesh.n_points:
                mesh.point_data[name] = scalars

            self.plotter.add_mesh(mesh, show_edges=show_edges)
            self.plotter.add_scalar_bar(title=name)
        else:
            self.plotter.add_mesh(mesh, color="white", show_edges=show_edges)

        self.plotter.reset_camera()