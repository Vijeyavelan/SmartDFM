"""Draft angle check module (skeleton)."""

from typing import Tuple
import numpy as np
import trimesh


def compute_draft_angles(
    mesh: trimesh.Trimesh,
    pull_direction: np.ndarray = np.array([0.0, 0.0, 1.0]),
) -> np.ndarray:
    """Compute draft angle between each face normal and the mold pull direction.

    Parameters
    ----------
    mesh : trimesh.Trimesh
    pull_direction : (3,) array-like
        Unit vector representing mold pull direction.

    Returns
    -------
    angles_deg : (F,) np.ndarray
        Draft angle in degrees for each face.
    """
    pull_dir = np.asarray(pull_direction, dtype=float)
    pull_dir /= np.linalg.norm(pull_dir) + 1e-12

    face_normals = mesh.face_normals
    # cos(theta) = n · d
    cos_theta = np.clip((face_normals @ pull_dir), -1.0, 1.0)
    angles_rad = np.arccos(np.abs(cos_theta))  # use abs: symmetric around pull axis
    angles_deg = np.degrees(angles_rad)
    return angles_deg
