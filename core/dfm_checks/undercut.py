# core/dfm_checks/undercut.py

import numpy as np

# Simple angle threshold for undercut classification (in degrees)
# Faces whose normal is more than this angle away from the pull direction
# are treated as "undercut" (facing too opposite to the pull).
DEFAULT_UNDERCUT_ANGLE_DEG = 90.0


def check_undercuts(
    faces: np.ndarray,
    face_normals: np.ndarray,
    num_vertices: int,
    pull_direction: np.ndarray,
    angle_threshold_deg: float = DEFAULT_UNDERCUT_ANGLE_DEG,
) -> dict:
    """
    Very simple undercut / back-draft heuristic.

    We treat faces whose normals are strongly opposed to the pull direction
    as "undercut" faces. This is not a full moldability solver, but it is
    a useful first-level flag for faces that the mold would have trouble
    clearing in the selected pull direction.

    Parameters
    ----------
    faces : (M, 3) int array
        Triangle indices into the vertex array.
    face_normals : (M, 3) float array
        Unit-length face normals (assumed).
    num_vertices : int
        Number of vertices (for building a vertex mask).
    pull_direction : (3,) float array
        Mold opening / ejection direction.
    angle_threshold_deg : float
        Faces whose normal forms an angle > this with the pull direction
        are treated as undercut.

    Returns
    -------
    result : dict
        {
          "status": "OK" or "WARNING",
          "message": str,
          "num_undercut_faces": int,
          "angle_threshold_deg": float,
          "max_undercut_angle_deg": float | None,
          "bad_face_mask": (M,) bool array,
          "bad_vertex_mask": (N,) bool array,
        }
    """
    if pull_direction is None:
        # Default to +Z if not specified
        pull_direction = np.array([0.0, 0.0, 1.0], dtype=float)

    pull_dir = np.asarray(pull_direction, dtype=float)
    norm = np.linalg.norm(pull_dir)
    if norm == 0:
        # Degenerate pull direction, fall back to +Z
        pull_dir = np.array([0.0, 0.0, 1.0], dtype=float)
        norm = 1.0
    pull_dir /= norm

    # Cosine of the threshold angle
    theta_rad = np.deg2rad(angle_threshold_deg)
    cos_threshold = np.cos(theta_rad)

    # Dot product between face normal and pull direction
    dots = np.einsum("ij,j->i", face_normals, pull_dir)
    # Clamp for numerical stability
    dots_clamped = np.clip(dots, -1.0, 1.0)
    angles_deg = np.degrees(np.arccos(dots_clamped))

    # Undercut condition: angle > threshold → dot < cos(threshold)
    bad_face_mask = dots < cos_threshold
    num_bad_faces = int(bad_face_mask.sum())

    if num_bad_faces > 0:
        status = "WARNING"
        max_angle = float(angles_deg[bad_face_mask].max())
        msg = (
            f"Undercut / back-draft faces detected: {num_bad_faces} faces "
            f"with angle > {angle_threshold_deg:.1f}° to pull direction "
            f"(max ~{max_angle:.1f}°)."
        )
    else:
        status = "OK"
        max_angle = None
        msg = (
            f"No undercut faces detected above {angle_threshold_deg:.1f}° "
            f"relative to pull direction."
        )

    # Build a simple vertex mask for possible future visualization
    bad_vertex_mask = np.zeros(num_vertices, dtype=bool)
    bad_face_indices = np.nonzero(bad_face_mask)[0]
    for fi in bad_face_indices:
        i0, i1, i2 = faces[fi]
        bad_vertex_mask[i0] = True
        bad_vertex_mask[i1] = True
        bad_vertex_mask[i2] = True

    return {
        "status": status,
        "message": msg,
        "num_undercut_faces": num_bad_faces,
        "angle_threshold_deg": float(angle_threshold_deg),
        "max_undercut_angle_deg": max_angle,
        "bad_face_mask": bad_face_mask,
        "bad_vertex_mask": bad_vertex_mask,
    }