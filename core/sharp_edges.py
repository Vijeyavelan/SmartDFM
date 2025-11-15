"""Sharp edge detection module (skeleton)."""

from typing import Tuple
import numpy as np
import trimesh


def detect_sharp_edges(
    mesh: trimesh.Trimesh,
    threshold_degrees: float = 150.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Detect sharp edges based on dihedral angle between adjacent faces.

    Parameters
    ----------
    mesh : trimesh.Trimesh
    threshold_degrees : float
        Edges with dihedral angle less than this are treated as sharp.

    Returns
    -------
    edge_indices : (E_s, 2) np.ndarray
        Vertex indices for sharp edges.
    dihedral_angles : (E_s,) np.ndarray
        Corresponding dihedral angles in degrees.
    """
    # trimesh provides dihedral angles per edge
    edges = mesh.edges_unique
    angles = mesh.edges_unique_dihedral  # radians; may contain NaN for boundaries

    # Convert to degrees, replace NaN with 180 (flat / boundary assumption)
    angles_deg = np.degrees(np.nan_to_num(angles, nan=180.0))
    mask_sharp = angles_deg < threshold_degrees

    return edges[mask_sharp], angles_deg[mask_sharp]
