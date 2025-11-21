# core/dfm_engine.py

import numpy as np

from core.dfm_checks.thickness import (
    compute_face_normals,
    compute_vertex_normals,
    check_local_wall_thickness,
    MIN_GLOBAL_THICKNESS,
    LOCAL_MIN_THICKNESS,
)
from core.dfm_checks.sharp_corners import (
    check_sharp_corners,
)


def run_all_checks(
    vertices: np.ndarray,
    faces: np.ndarray,
    min_global_thickness: float = MIN_GLOBAL_THICKNESS,
    min_local_thickness: float = LOCAL_MIN_THICKNESS,
) -> dict:
    """
    Main DFM pipeline for SmartDFM (Injection Molding MVP).

    - Computes basic geometry (bbox, triangle count)
    - Runs global thickness check
    - Runs local wall thickness check
    - Runs sharp corner check
    - Returns a single results dict consumed by the UI
    """
    results: dict = {}

    # ---- Geometry ----
    tri_count = faces.shape[0]
    min_bounds = vertices.min(axis=0)
    max_bounds = vertices.max(axis=0)
    extents = max_bounds - min_bounds

    results["triangles"] = int(tri_count)
    results["bbox"] = {
        "min": min_bounds,
        "max": max_bounds,
        "extents": extents,
    }

    # ---- Normals ----
    face_normals, face_areas = compute_face_normals(vertices, faces)
    vertex_normals = compute_vertex_normals(vertices, faces, face_normals, face_areas)

    results["normals_info"] = {
        "num_faces": int(face_normals.shape[0]),
        "num_vertices": int(vertex_normals.shape[0]),
    }

    checks: dict = {}
    results["checks"] = checks

    # ---- Global thickness check ----
    smallest_dim = float(extents.min())
    if smallest_dim < min_global_thickness:
        g_status = "WARNING"
        g_msg = (
            f"Global thin-part issue: smallest dimension "
            f"{smallest_dim:.3f} < min {min_global_thickness:.3f}."
        )
    else:
        g_status = "OK"
        g_msg = (
            f"Global thickness OK: smallest dimension "
            f"{smallest_dim:.3f} ≥ min {min_global_thickness:.3f}."
        )

    checks["global_thickness"] = {
        "status": g_status,
        "message": g_msg,
        "smallest_dimension": smallest_dim,
        "min_allowed": min_global_thickness,
    }

    # ---- Local wall thickness check ----
    local_result = check_local_wall_thickness(
        vertices,
        faces,
        vertex_normals,
        extents,
        min_thickness=min_local_thickness,
    )
    checks["local_thickness"] = local_result

    # ---- Sharp corner check ----
    corner_result = check_sharp_corners(
        faces=faces,
        face_normals=face_normals,
        num_vertices=vertices.shape[0],
    )
    checks["sharp_corners"] = corner_result

    # ---- Summary ----
    l_status = local_result.get("status", "UNKNOWN")
    c_status = corner_result.get("status", "UNKNOWN")

    results["summary"] = (
        f"DFM – Global thickness: {g_status}. "
        f"Local thickness: {l_status}. "
        f"Sharp corners: {c_status}."
    )

    return results