# core/stl_loader.py

from stl import mesh
import numpy as np

def load_stl(filepath: str):
    """
    Load an STL file and return vertices and faces suitable for rendering.
    """
    m = mesh.Mesh.from_file(filepath)

    # Each STL triangle has 3 vertices; we flatten and then unique them
    vertices_raw = m.vectors.reshape(-1, 3)  # (n_triangles*3, 3)

    # Get unique vertices and indices
    vertices, unique_indices = np.unique(vertices_raw, axis=0, return_inverse=True)

    # Faces are groups of three indices
    faces = unique_indices.reshape(-1, 3)

    return vertices, faces