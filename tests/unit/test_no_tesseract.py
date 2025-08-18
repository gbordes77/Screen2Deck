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
    """Source code must not import or use tesseract."""
    from pathlib import Path
    backend_dir = Path(__file__).parent.parent.parent / "backend"
    
    for py_file in backend_dir.rglob("*.py"):
        if "test" in str(py_file):  # Skip test files
            continue
        content = py_file.read_text().lower()
        assert "tesseract" not in content, f"Found tesseract reference in {py_file}"
        assert "pytesseract" not in content, f"Found pytesseract reference in {py_file}"