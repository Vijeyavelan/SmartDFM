"""Undercut detection module (skeleton)."""

import numpy as np
import trimesh


def detect_undercuts(
    mesh: trimesh.Trimesh,
    pull_direction: np.ndarray = np.array([0.0, 0.0, 1.0]),
) -> np.ndarray:
    """Very simple undercut indicator per face (placeholder).

    Current heuristic:
    - Faces whose normal is significantly opposing the pull direction
      are flagged as potential undercuts.

    In the final version, extend this with ray casting along the pull
    direction to detect real geometric obstructions.

    Returns
    -------
    flags : (F,) np.ndarray of bool
        True for potential undercut faces.
    """
    pull_dir = np.asarray(pull_direction, dtype=float)
    pull_dir /= np.linalg.norm(pull_dir) + 1e-12

    face_normals = mesh.face_normals
    cos_theta = face_normals @ pull_dir
    # Faces pointing "backwards" relative to pull direction
    flags = cos_theta < 0.0
    return flags
