"""PyVista-based visualization helpers."""

from typing import Optional

import numpy as np
import pyvista as pv


def show_mesh(
    pv_mesh: pv.PolyData,
    scalars: Optional[np.ndarray] = None,
    title: str = "SmartDFM Viewer",
    scalar_bar_title: Optional[str] = None,
) -> None:
    """Display a mesh in an interactive PyVista window.

    Parameters
    ----------
    pv_mesh : pv.PolyData
        Mesh to display.
    scalars : array-like, optional
        Per-face or per-vertex scalars used for color mapping.
    title : str
        Window title.
    scalar_bar_title : str, optional
        Label for the scalar bar.
    """
    plotter = pv.Plotter()
    if scalars is not None:
        # Attach scalars; PyVista will infer if cell or point data based on size
        pv_mesh = pv_mesh.copy()
        if len(scalars) == pv_mesh.n_cells:
            pv_mesh.cell_data[scalar_bar_title or "scalars"] = scalars
        elif len(scalars) == pv_mesh.n_points:
            pv_mesh.point_data[scalar_bar_title or "scalars"] = scalars

        plotter.add_mesh(pv_mesh, show_edges=True)
    else:
        plotter.add_mesh(pv_mesh, color="white", show_edges=True)

    plotter.add_axes()
    plotter.show(title=title)
