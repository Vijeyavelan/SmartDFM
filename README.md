# SmartDFM

SmartDFM is an open-source, Python-based Design for Manufacturability (DFM) assistant
for mechanical parts such as injection-molded and machined components.

This skeleton provides:
- Geometry loading (STL)
- Basic PyVista visualization
- A modular core for DFM rule modules
- A PyQt6 UI skeleton ready for extension

## Quick start

```bash
cd SmartDFM
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt

python main.py sample_parts/example.stl   # once you add a sample STL
```

## Project layout

- `core/` – geometry processing and DFM rule logic
- `visualization/` – 3D display utilities (PyVista)
- `ui/` – PyQt6-based user interface
- `tests/` – unit tests
- `sample_parts/` – put your STL test parts here
