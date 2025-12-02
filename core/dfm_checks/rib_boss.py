# core/dfm_checks/rib_boss.py

import numpy as np

# Simple config: how much thicker than nominal wall is allowed
DEFAULT_RIB_BOSS_FACTOR = 1.5  # "thick region" if > 1.5x nominal wall


def check_rib_boss_thickness(
    per_vertex_thickness: np.ndarray,
    base_wall_thickness: float | None = None,
    factor: float = DEFAULT_RIB_BOSS_FACTOR,
) -> dict:
    """
    Very simple heuristic to flag regions that are significantly thicker
    than the nominal wall thickness. These are likely rib / boss bases
    or chunky intersections that can lead to sink marks or cooling issues.

    Parameters
    ----------
    per_vertex_thickness : (N,) float array
        Local thickness estimates at each vertex (from local thickness check).
    base_wall_thickness : float or None
        If None, we'll estimate it from the thickness distribution
        (e.g., median of valid values).
    factor : float
        Allowed multiple of the base wall thickness. Values above
        base * factor are treated as over-thick regions.

    Returns
    -------
    result : dict
        {
          "status": "OK" or "WARNING",
          "message": str,
          "base_wall_thickness": float,
          "max_thickness": float,
          "factor": float,
          "threshold": float,
          "num_over_thick_vertices": int,
          "bad_vertex_mask": (N,) bool array,
        }
    """
    t = np.asarray(per_vertex_thickness, dtype=float)

    finite_mask = np.isfinite(t)
    if not finite_mask.any():
        return {
            "status": "UNKNOWN",
            "message": "No valid local thickness data for rib/boss check.",
            "base_wall_thickness": None,
            "max_thickness": None,
            "factor": factor,
            "threshold": None,
            "num_over_thick_vertices": 0,
            "bad_vertex_mask": np.zeros_like(t, dtype=bool),
        }

    t_valid = t[finite_mask]

    if base_wall_thickness is None:
        # Use median as a robust estimate of nominal wall thickness
        base_wall = float(np.median(t_valid))
    else:
        base_wall = float(base_wall_thickness)

    threshold = base_wall * float(factor)
    bad_vertex_mask = finite_mask & (t > threshold)
    num_bad = int(bad_vertex_mask.sum())
    max_thick = float(t_valid.max())

    if num_bad > 0:
        status = "WARNING"
        msg = (
            f"Rib/Boss thickness: {num_bad} vertices exceed "
            f"{factor:.2f}× nominal wall thickness "
            f"(nominal ~{base_wall:.3f}, max ~{max_thick:.3f})."
        )
    else:
        status = "OK"
        msg = (
            f"Rib/Boss thickness OK: no regions above "
            f"{factor:.2f}× nominal wall thickness "
            f"(nominal ~{base_wall:.3f}, max ~{max_thick:.3f})."
        )

    return {
        "status": status,
        "message": msg,
        "base_wall_thickness": base_wall,
        "max_thickness": max_thick,
        "factor": float(factor),
        "threshold": float(threshold),
        "num_over_thick_vertices": num_bad,
        "bad_vertex_mask": bad_vertex_mask,
    }