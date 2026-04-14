"""Security test: ensure Tesseract is NEVER used."""
import shutil
import subprocess
import sys
import pytest

def test_no_tesseract_binary():
    """Tesseract binary must NOT be installed."""
    assert shutil.which("tesseract") is None, "tesseract must NOT be installed"

def test_no_pytesseract_import():
    """pytesseract package must NOT be importable."""
    proc = subprocess.run(
        [sys.executable, "-c", "import pkgutil; print(bool(pkgutil.find_loader('pytesseract')))"],
        capture_output=True,
        text=True
    )
    assert proc.stdout.strip() == "False", "pytesseract must NOT be present"

def test_no_tesseract_in_requirements():
    """Requirements files must not contain tesseract."""
    from pathlib import Path
    backend_dir = Path(__file__).parent.parent.parent / "backend"
    
    for req_file in backend_dir.glob("requirements*.txt"):
        content = req_file.read_text().lower()
        assert "tesseract" not in content, f"Found tesseract in {req_file.name}"
        assert "pytesseract" not in content, f"Found pytesseract in {req_file.name}"

def test_no_tesseract_in_code():
    """Source code must not import the tesseract / pytesseract Python
    modules.

    We match on actual import statements (``import pytesseract``,
    ``from pytesseract import ...``) rather than loose substring
    because the project legitimately mentions the word "tesseract" in
    a handful of places whose purpose is to *forbid* it — notably
    ``backend/app/core/determinism.py`` which raises a RuntimeError
    when the binary is present, and ``backend/app/api/health.py``
    which exposes an "anti_tesseract" health field.
    """
    import re
    from pathlib import Path

    backend_dir = Path(__file__).parent.parent.parent / "backend"
    import_pattern = re.compile(
        r"^\s*(?:import|from)\s+(?:py)?tesseract\b", re.MULTILINE
    )

    for py_file in backend_dir.rglob("*.py"):
        if "test" in str(py_file):  # Skip test files
            continue
        content = py_file.read_text()
        match = import_pattern.search(content)
        assert match is None, (
            f"Found tesseract import in {py_file}: {match.group(0) if match else ''}"
        )