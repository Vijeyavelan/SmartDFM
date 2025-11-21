# core/dfm_checks/sharp_corners.py

import numpy as np

# Default threshold for injection molding sharp-corner detection
SHARP_ANGLE_THRESHOLD_DEG = 60.0


def check_sharp_corners(
    faces: np.ndarray,
    face_normals: np.ndarray,
    num_vertices: int,
    angle_threshold_deg: float = SHARP_ANGLE_THRESHOLD_DEG,
):
    """
    Sharp internal/external corner detection based on dihedral angles.
    """

    # Build edge -> face adjacency map
    edge_to_faces = {}
    for f_idx, (i0, i1, i2) in enumerate(faces):
        for a, b in ((i0, i1), (i1, i2), (i2, i0)):
            e = tuple(sorted((a, b)))
            edge_to_faces.setdefault(e, []).append(f_idx)

    sharp_edges = []
    edge_angles = []

    for (v0, v1), f_list in edge_to_faces.items():
        if len(f_list) != 2:
            # Non-manifold or boundary edge — skip for now
            continue

        f1, f2 = f_list
        n1 = face_normals[f1]
        n2 = face_normals[f2]

        dot = np.clip(np.dot(n1, n2), -1.0, 1.0)
        angle_rad = np.arccos(dot)
        angle_deg = float(np.degrees(angle_rad))

        if angle_deg > angle_threshold_deg:
            sharp_edges.append((v0, v1))
            edge_angles.append(angle_deg)

    # Vertex-level mask for visualization
    corner_vertex_mask = np.zeros(num_vertices, dtype=bool)
    for (v0, v1) in sharp_edges:
        corner_vertex_mask[v0] = True
        corner_vertex_mask[v1] = True

    num_sharp = len(sharp_edges)
    max_angle = max(edge_angles) if edge_angles else 0.0

    if num_sharp > 0:
        status = "WARNING"
        message = (
            f"{num_sharp} sharp edges exceed {angle_threshold_deg:.1f}°.\n"
            f"Max corner angle = {max_angle:.1f}°.\n"
            f"For injection molding, consider fillets to reduce stress concentration."
        )
    else:
        status = "OK"
        message = (
            f"No edges exceed {angle_threshold_deg:.1f}°.\n"
            "Corner sharpness appears acceptable."
        )

    return {
        "status": status,
        "message": message,
        "num_sharp_edges": num_sharp,
        "angle_threshold_deg": angle_threshold_deg,
        "max_sharp_angle_deg": max_angle,
        "corner_vertex_mask": corner_vertex_mask,
    }