# core/dfm_checks/draft.py

import numpy as np
from typing import Optional

# Default minimum draft angle (degrees)
DRAFT_MIN_ANGLE_DEG = 2.0


def check_draft_angle(
    faces: np.ndarray,
    face_normals: np.ndarray,
    num_vertices: int,
    pull_direction: Optional[np.ndarray] = None,
    min_draft_angle_deg: float = DRAFT_MIN_ANGLE_DEG,
):
    """
    Draft angle check for injection molding.

    Default pull direction = +Z.

    For each face:
        1. Compute angle between face normal and pull direction.
        2. Convert to "draft angle":
              draft = |90° - measured_angle|
        3. Faces with draft < threshold → WARNING.

    Returns:
        dict with:
            status ("OK" or "WARNING")
            message
            min_draft_angle
            num_bad_faces
            angle_threshold_deg
            per_face_draft_angle
            bad_face_mask
            bad_vertex_mask
    """

    # Default pull direction = +Z
    if pull_direction is None:
        pull_direction = np.array([0.0, 0.0, 1.0], dtype=float)

    pull_dir = np.array(pull_direction, dtype=float)
    norm = np.linalg.norm(pull_dir)
    if norm == 0:
        pull_dir = np.array([0.0, 0.0, 1.0])
    else:
        pull_dir /= norm

    # Angle between each face normal and pull direction
    dots = np.einsum("ij,j->i", face_normals, pull_dir)
    dots = np.clip(dots, -1.0, 1.0)
    face_angle_rad = np.arccos(dots)
    face_angle_deg = np.degrees(face_angle_rad)

    # Draft angle = |90° - measured_angle|
    draft_angles = np.abs(90.0 - face_angle_deg)

    bad_face_mask = draft_angles < min_draft_angle_deg
    num_bad_faces = int(bad_face_mask.sum())

    # Per-vertex mask: any vertex belonging to a bad face is marked
    bad_vertex_mask = np.zeros(num_vertices, dtype=bool)
    bad_faces = np.nonzero(bad_face_mask)[0]
    for f in bad_faces:
        i0, i1, i2 = faces[f]
        bad_vertex_mask[i0] = True
        bad_vertex_mask[i1] = True
        bad_vertex_mask[i2] = True

    min_draft_angle = float(draft_angles.min()) if draft_angles.size > 0 else 0.0

    if num_bad_faces > 0:
        status = "WARNING"
        msg = (
            f"{num_bad_faces} faces have draft angle < {min_draft_angle_deg:.1f}°. "
            f"Minimum found = {min_draft_angle:.2f}°."
        )
    else:
        status = "OK"
        msg = f"All faces meet the minimum draft angle of {min_draft_angle_deg:.1f}°."

    return {
        "status": status,
        "message": msg,
        "min_draft_angle": min_draft_angle,
        "num_bad_faces": num_bad_faces,
        "angle_threshold_deg": min_draft_angle_deg,
        "per_face_draft_angle": draft_angles,
        "bad_face_mask": bad_face_mask,
        "bad_vertex_mask": bad_vertex_mask,
    }