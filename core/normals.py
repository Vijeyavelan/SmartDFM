"""Normal and basic geometric feature computation."""

from typing import Tuple
import numpy as np
import trimesh


def compute_face_and_vertex_normals(mesh: trimesh.Trimesh) -> Tuple[np.ndarray, np.ndarray]:
    """Compute face and vertex normals for a mesh.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Input triangle mesh.

    Returns
    -------
    face_normals : (F, 3) np.ndarray
        Per-face unit normals.
    vertex_normals : (V, 3) np.ndarray
        Per-vertex unit normals.
    """
    # trimesh lazily computes and caches these
    face_normals = mesh.face_normals
    vertex_normals = mesh.vertex_normals
    return face_normals, vertex_normals
