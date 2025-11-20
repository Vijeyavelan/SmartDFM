# core/dfm_checks.py

import numpy as np
from scipy.spatial import cKDTree
from typing import Optional

# Configuration values (can later be controlled from UI)
MIN_GLOBAL_THICKNESS = 0.5   # model units
LOCAL_MIN_THICKNESS = 0.8    # model units


# ---------------------------------------------------------
#  Face Normals
# ---------------------------------------------------------
def compute_face_normals(vertices: np.ndarray, faces: np.ndarray):
    """Compute per-face normals and triangle areas."""
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    e1 = v1 - v0
    e2 = v2 - v0

    normals = np.cross(e1, e2)
    lengths = np.linalg.norm(normals, axis=1)

    safe_lengths = np.where(lengths == 0, 1.0, lengths)

    face_normals = normals / safe_lengths[:, np.newaxis]
    face_areas = 0.5 * lengths

    return face_normals, face_areas


# ---------------------------------------------------------
#  Vertex Normals
# ---------------------------------------------------------
def compute_vertex_normals(
    vertices: np.ndarray,
    faces: np.ndarray,
    face_normals: np.ndarray,
    face_areas: Optional[np.ndarray] = None,
):
    """Compute averaged per-vertex normals."""
    num_vertices = vertices.shape[0]
    vertex_normals = np.zeros((num_vertices, 3), dtype=float)

    if face_areas is None:
        weights = np.ones(face_normals.shape[0])
    else:
        weights = face_areas

    for face_idx, (i0, i1, i2) in enumerate(faces):
        w = weights[face_idx]
        n = face_normals[face_idx] * w
        vertex_normals[i0] += n
        vertex_normals[i1] += n
        vertex_normals[i2] += n

    lengths = np.linalg.norm(vertex_normals, axis=1)
    safe_lengths = np.where(lengths == 0, 1.0, lengths)
    return vertex_normals / safe_lengths[:, np.newaxis]


# ---------------------------------------------------------
#  Local Wall Thickness (KD-tree + fallback)
# ---------------------------------------------------------
def check_local_wall_thickness(
    vertices: np.ndarray,
    faces: np.ndarray,
    vertex_normals: np.ndarray,
    extents: np.ndarray,
    min_thickness: float = LOCAL_MIN_THICKNESS,
):
    """
    Approximate local wall thickness at each vertex using:
      - KD-tree projection search
      - Fallback to bounding-box min dimension
    """
    num_vertices = vertices.shape[0]

    # KD-tree on vertices
    tree = cKDTree(vertices)

    # Per-vertex thickness estimates
    thickness = np.full(num_vertices, np.inf)
    k_neighbors = min(32, num_vertices)

    # Try to estimate thickness via normals + KD-tree
    for i in range(num_vertices):
        origin = vertices[i]
        n = vertex_normals[i]

        if np.allclose(n, 0):
            continue

        distances, indices = tree.query(origin, k=k_neighbors)

        if np.isscalar(indices):
            indices = np.array([indices])
            distances = np.array([distances])

        local_min = np.inf

        for d, j in zip(distances, indices):
            if j == i:
                continue

            vec = vertices[j] - origin
            proj_len = np.dot(vec, n)

            if proj_len > 0 and proj_len < local_min:
                local_min = proj_len

        if local_min < np.inf:
            thickness[i] = local_min

    # Try KD-tree results
    finite_mask = np.isfinite(thickness)

    if finite_mask.any():
        # KD-tree thickness computed
        global_min_th = float(thickness[finite_mask].min())
        thin_mask = finite_mask & (thickness < min_thickness)
        num_thin = int(thin_mask.sum())

        if num_thin > 0:
            status = "WARNING"
            msg = (
                f"Local wall thickness issue: min ~{global_min_th:.3f} "
                f"< target {min_thickness:.3f} (model units) at {num_thin} vertices."
            )
        else:
            status = "OK"
            msg = (
                f"Local wall thickness OK: min ~{global_min_th:.3f} "
                f"≥ target {min_thickness:.3f}."
            )

        return {
            "status": status,
            "message": msg,
            "min_thickness": global_min_th,
            "num_thin_vertices": num_thin,
            "threshold": float(min_thickness),
            "per_vertex_thickness": thickness,
        }

    # -----------------------------------------------------
    # Fallback (flat meshes, low vertex count, single walls)
    # -----------------------------------------------------
    approx_thickness = float(extents.min())

    if approx_thickness < min_thickness:
        status = "WARNING"
        msg = (
            f"Local thickness fallback: approx thickness ~{approx_thickness:.3f} "
            f"< target {min_thickness:.3f}."
        )
    else:
        status = "OK"
        msg = (
            f"Local thickness fallback: approx thickness ~{approx_thickness:.3f} "
            f"≥ target {min_thickness:.3f}."
        )

    return {
        "status": status,
        "message": msg,
        "min_thickness": approx_thickness,
        "num_thin_vertices": 0,
        "threshold": float(min_thickness),
        "per_vertex_thickness": thickness,   # mostly inf, acceptable for fallback
    }


# ---------------------------------------------------------
#  DFM Pipeline (Global + Local)
# ---------------------------------------------------------
def run_all_checks(vertices: np.ndarray, faces: np.ndarray) -> dict:
    """Main DFM check pipeline."""
    results: dict = {}

    # Geometry
    tri_count = faces.shape[0]
    min_bounds = vertices.min(axis=0)
    max_bounds = vertices.max(axis=0)
    extents = max_bounds - min_bounds

    results["triangles"] = int(tri_count)
    results["bbox"] = {"min": min_bounds, "max": max_bounds, "extents": extents}

    # Normals
    face_normals, face_areas = compute_face_normals(vertices, faces)
    vertex_normals = compute_vertex_normals(vertices, faces, face_normals, face_areas)

    results["normals_info"] = {
        "num_faces": int(face_normals.shape[0]),
        "num_vertices": int(vertex_normals.shape[0]),
    }

    # Global Thickness
    smallest_dim = float(extents.min())
    if smallest_dim < MIN_GLOBAL_THICKNESS:
        g_status = "WARNING"
        g_msg = (
            f"Global thin-part issue: smallest dimension "
            f"{smallest_dim:.3f} < min {MIN_GLOBAL_THICKNESS:.3f}."
        )
    else:
        g_status = "OK"
        g_msg = (
            f"Global thickness OK: smallest dimension "
            f"{smallest_dim:.3f} ≥ min {MIN_GLOBAL_THICKNESS:.3f}."
        )

    results["checks"] = {
        "global_thickness": {
            "status": g_status,
            "message": g_msg,
            "smallest_dimension": smallest_dim,
            "min_allowed": MIN_GLOBAL_THICKNESS,
        }
    }

    # Local Thickness
    local_result = check_local_wall_thickness(
        vertices,
        faces,
        vertex_normals,
        extents,
        min_thickness=LOCAL_MIN_THICKNESS,
    )
    results["checks"]["local_thickness"] = local_result

    # Summary
    l_status = local_result.get("status", "UNKNOWN")

    results["summary"] = (
        f"DFM – Global thickness: {g_status}. Local thickness: {l_status}."
    )

    return results