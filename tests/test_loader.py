"""Basic smoke test for the mesh loader."""

import pytest
from core.loader import load_mesh


def test_loader_missing_file():
    with pytest.raises(FileNotFoundError):
        load_mesh("nonexistent.stl")
