# core/dfm_checks/thickness.py

import numpy as np
from scipy.spatial import cKDTree


MIN_GLOBAL_THICKNESS = 0.5
LOCAL_MIN_THICKNESS = 0.8


def compute_face_normals(vertices, faces):
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    e1 = v1 - v0
    e2 = v2 - v0

    normals = np.cross(e1, e2)
    lengths = np.linalg.norm(normals, axis=1)
    safe = np.where(lengths == 0, 1.0, lengths)

    return normals / safe[:, None], 0.5 * lengths


def compute_vertex_normals(vertices, faces, face_normals, face_areas):
    num_vertices = len(vertices)
    vertex_normals = np.zeros((num_vertices, 3))

    for f_idx, (i0, i1, i2) in enumerate(faces):
        w = face_areas[f_idx]
        n = face_normals[f_idx] * w
        vertex_normals[i0] += n
        vertex_normals[i1] += n
        vertex_normals[i2] += n

    lengths = np.linalg.norm(vertex_normals, axis=1)
    safe = np.where(lengths == 0, 1.0, lengths)
    return vertex_normals / safe[:, None]


def check_local_wall_thickness(vertices, faces, vertex_normals, extents, min_thickness):
    num_vertices = len(vertices)
    tree = cKDTree(vertices)
    thickness = np.full(num_vertices, np.inf)

    k_neigh = min(32, num_vertices)

    for i in range(num_vertices):
        origin = vertices[i]
        n = vertex_normals[i]
        if np.allclose(n, 0):
            continue

        d, idx = tree.query(origin, k=k_neigh)
        if np.isscalar(idx):
            idx = [idx]

        local_min = np.inf

        for j in idx:
            if j == i:
                continue
            v = vertices[j]
            proj = np.dot(v - origin, n)
            if proj > 0 and proj < local_min:
                local_min = proj

        if local_min < np.inf:
            thickness[i] = local_min

    # If any finite thickness exists
    mask = np.isfinite(thickness)
    if mask.any():
        min_local = float(thickness[mask].min())
        thin_mask = mask & (thickness < min_thickness)
        num_thin = int(thin_mask.sum())

        if num_thin > 0:
            status = "WARNING"
            msg = (
                f"Minimum local thickness {min_local:.3f} < "
                f"required {min_thickness:.3f}."
            )
        else:
            status = "OK"
            msg = (
                f"Minimum local thickness {min_local:.3f} ≥ "
                f"required {min_thickness:.3f}."
            )

        return {
            "status": status,
            "message": msg,
            "min_thickness": min_local,
            "num_thin_vertices": num_thin,
            "threshold": min_thickness,
            "per_vertex_thickness": thickness,
        }

    # Fallback: use bounding box min dimension
    fallback = float(extents.min())
    if fallback < min_thickness:
        status = "WARNING"
        msg = (
            f"Fallback local thickness {fallback:.3f} < "
            f"required {min_thickness:.3f}."
        )
    else:
        status = "OK"
        msg = (
            f"Fallback local thickness {fallback:.3f} ≥ "
            f"required {min_thickness:.3f}."
        )

    return {
        "status": status,
        "message": msg,
        "min_thickness": fallback,
        "num_thin_vertices": 0,
        "threshold": min_thickness,
        "per_vertex_thickness": thickness,
    }