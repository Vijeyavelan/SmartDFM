"""Overall manufacturability scoring utilities (skeleton)."""

from dataclasses import dataclass


@dataclass
class DFMMetrics:
    num_faces: int
    num_thickness_violations: int = 0
    num_draft_violations: int = 0
    num_undercut_faces: int = 0
    num_sharp_edges: int = 0


def compute_score(metrics: DFMMetrics) -> float:
    """Compute a simple manufacturability score from 0–100.

    This is a placeholder formula; you can refine the weights as you calibrate
    against real guidelines.

    Parameters
    ----------
    metrics : DFMMetrics

    Returns
    -------
    score : float
        Manufacturability score (0–100).
    """
    if metrics.num_faces <= 0:
        return 0.0

    # Simple normalized ratios
    t_ratio = metrics.num_thickness_violations / metrics.num_faces
    d_ratio = metrics.num_draft_violations / metrics.num_faces
    u_ratio = metrics.num_undercut_faces / metrics.num_faces
    s_ratio = metrics.num_sharp_edges / max(metrics.num_faces, 1)

    score = 100.0
    score -= 40.0 * t_ratio
    score -= 30.0 * d_ratio
    score -= 20.0 * u_ratio
    score -= 10.0 * s_ratio

    return max(0.0, min(100.0, score))
