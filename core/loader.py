"""Mesh loading utilities for SmartDFM."""

from pathlib import Path
from typing import Tuple

import trimesh
import pyvista as pv


def load_mesh(path: str) -> Tuple[trimesh.Trimesh, pv.PolyData]:
    """Load a mesh from an STL (or other supported) file.

    Parameters
    ----------
    path : str
        Path to the mesh file.

    Returns
    -------
    tri_mesh : trimesh.Trimesh
        The raw trimesh representation.
    pv_mesh : pyvista.PolyData
        A PyVista version suitable for visualization.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the loaded geometry is empty or invalid.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Mesh file not found: {p}")

    tri_mesh = trimesh.load_mesh(str(p))
    if tri_mesh.is_empty:
        raise ValueError(f"Loaded mesh is empty: {p}")

    # Convert to PyVista PolyData
    pv_mesh = pv.wrap(tri_mesh.vertices, tri_mesh.faces.reshape(-1, 4)[:, 1:])
    # Alternative: pv.wrap(tri_mesh) also often works, but this is explicit.

    return tri_mesh, pv_mesh
