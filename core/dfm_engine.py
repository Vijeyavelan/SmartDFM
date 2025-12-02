# core/dfm_engine.py

import numpy as np
from typing import Optional

from core.dfm_checks.draft import check_draft_angle
from core.dfm_checks.thickness import (
    compute_face_normals,
    compute_vertex_normals,
    check_local_wall_thickness,
    MIN_GLOBAL_THICKNESS,
    LOCAL_MIN_THICKNESS,
)
from core.dfm_checks.sharp_corners import check_sharp_corners
from core.dfm_checks.undercut import check_undercuts
from core.dfm_checks.rib_boss import check_rib_boss_thickness

def run_all_checks(
    vertices: np.ndarray,
    faces: np.ndarray,
    min_global_thickness: float = MIN_GLOBAL_THICKNESS,
    min_local_thickness: float = LOCAL_MIN_THICKNESS,
    pull_direction: Optional[np.ndarray] = None,
) -> dict:
    """
    Main DFM pipeline for SmartDFM (Injection Molding MVP).

    Parameters
    ----------
    vertices : (N, 3) float array
    faces    : (M, 3) int array
    min_global_thickness : float
    min_local_thickness  : float
    pull_direction       : (3,) float array or None
        Draft / ejection direction in model coordinates.
        If None, the draft check will default to +Z inside check_draft_angle().
    """

    results: dict = {}

    # -----------------------------------------------
    # Geometry
    # -----------------------------------------------
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

    # -----------------------------------------------
    # Normals
    # -----------------------------------------------
    face_normals, face_areas = compute_face_normals(vertices, faces)
    vertex_normals = compute_vertex_normals(vertices, faces, face_normals, face_areas)

    results["normals_info"] = {
        "num_faces": int(face_normals.shape[0]),
        "num_vertices": int(vertex_normals.shape[0]),
    }

    checks: dict = {}
    results["checks"] = checks

    # -----------------------------------------------
    # Global thickness
    # -----------------------------------------------
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

    # -----------------------------------------------
    # Local thickness
    # -----------------------------------------------
    local_result = check_local_wall_thickness(
        vertices,
        faces,
        vertex_normals,
        extents,
        min_thickness=min_local_thickness,
    )
    checks["local_thickness"] = local_result

    # -----------------------------------------------
    # Rib / Boss thickness check (over-thick regions)
    # -----------------------------------------------
    per_vertex_thickness = local_result.get("per_vertex_thickness", None)
    if per_vertex_thickness is not None:
        rib_boss_result = check_rib_boss_thickness(
            per_vertex_thickness=per_vertex_thickness,
            base_wall_thickness=None,  # let the function estimate it
        )
    else:
        rib_boss_result = {
            "status": "UNKNOWN",
            "message": "No local thickness data available for rib/boss check.",
            "base_wall_thickness": None,
            "max_thickness": None,
            "factor": None,
            "threshold": None,
            "num_over_thick_vertices": 0,
            "bad_vertex_mask": None,
        }

    checks["rib_boss"] = rib_boss_result

    # -----------------------------------------------
    # Sharp corners
    # -----------------------------------------------
    corner_result = check_sharp_corners(
        faces=faces,
        face_normals=face_normals,
        num_vertices=vertices.shape[0],
    )
    checks["sharp_corners"] = corner_result

    # -----------------------------------------------
    # Draft angle (using selected pull_direction)
    # -----------------------------------------------
    draft_result = check_draft_angle(
        faces=faces,
        face_normals=face_normals,
        num_vertices=vertices.shape[0],
        pull_direction=pull_direction,  # may be None → defaults to +Z inside the function
    )
    checks["draft_angle"] = draft_result
    
    # -----------------------------------------------
    # Undercuts
    # -----------------------------------------------
    undercut_result = check_undercuts(
        faces=faces,
        face_normals=face_normals,
        num_vertices=vertices.shape[0],
        pull_direction=pull_direction,  # may be None → defaults to +Z inside the function
    )
    checks["undercuts"] = undercut_result

    # -----------------------------------------------
    # Summary
    # -----------------------------------------------
    l_status = local_result.get("status", "UNKNOWN")
    c_status = corner_result.get("status", "UNKNOWN")
    d_status = draft_result.get("status", "UNKNOWN")
    u_status = undercut_result.get("status", "UNKNOWN")
    rb_status = rib_boss_result.get("status", "UNKNOWN")

    results["summary"] = (
        f"DFM – Global thickness: {g_status}. "
        f"Local thickness: {l_status}. "
        f"Sharp corners: {c_status}. "
        f"Draft angle: {d_status}."
        f" Undercuts: {u_status}."
        f"Rib/Boss thickness: {rb_status}."
    )

    return results