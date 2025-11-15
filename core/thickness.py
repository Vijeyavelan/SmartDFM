"""Wall thickness analysis module (skeleton)."""

from typing import Optional
import numpy as np
import trimesh


def estimate_wall_thickness(mesh: trimesh.Trimesh) -> np.ndarray:
    """Estimate wall thickness per face (very simple placeholder implementation).

    This is a **placeholder**. In the final project, replace with a more robust
    ray-casting or nearest-opposite-surface method.

    Parameters
    ----------
    mesh : trimesh.Trimesh

    Returns
    -------
    thickness_per_face : (F,) np.ndarray
        Dummy values for now (e.g., constant).
    """
    num_faces = len(mesh.faces)
    # TODO: implement real thickness computation
    thickness_per_face = np.ones(num_faces, dtype=float)
    return thickness_per_face
