"""Packaging smoke test: verify wheel can be built and installed independently."""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_wheel_build():
    """Verify that a wheel can be built."""
    result = subprocess.run(
        ["poetry", "build", "--format", "wheel"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Wheel build failed:\n{result.stderr}"
    # Either fresh build or already exists
    assert "built" in result.stderr.lower() or result.returncode == 0


def test_wheel_contains_package():
    """Verify that the wheel contains the postbox package."""
    import zipfile

    wheel_dir = Path(__file__).parent.parent / "dist"
    wheel_files = list(wheel_dir.glob("postbox-*.whl"))
    assert len(wheel_files) > 0, f"No wheel found in {wheel_dir}"

    wheel_file = wheel_files[-1]  # Latest
    with zipfile.ZipFile(wheel_file) as z:
        names = z.namelist()
        # Check for package files
        assert any("postbox/__init__.py" in n for n in names), "postbox package not found in wheel"
        assert any("postbox/api.py" in n for n in names), "postbox/api.py not found in wheel"
        assert any("entry_points.txt" in n for n in names), "entry_points.txt not found in wheel"


def test_wheel_install_isolated():
    """Verify that wheel installs into a clean venv and imports work."""

    wheel_dir = Path(__file__).parent.parent / "dist"
    wheel_files = sorted(wheel_dir.glob("postbox-*.whl"))
    assert len(wheel_files) > 0, f"No wheel found in {wheel_dir}"

    wheel_file = wheel_files[-1]

    # Create isolated temp venv
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = Path(tmpdir) / "test_venv"

        # Create venv
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"venv creation failed:\n{result.stderr}"

        # Install wheel
        python_exe = venv_dir / "bin" / "python"
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", str(wheel_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Wheel install failed:\n{result.stderr}"

        # Test import from temp directory (not from repo)
        result = subprocess.run(
            [
                str(python_exe),
                "-c",
                "import postbox; print(postbox.__file__)",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Import failed:\n{result.stderr}"
        assert str(venv_dir) in result.stdout, f"postbox imported from outside venv: {result.stdout}"

        # Test that postbox-api command exists
        postbox_api = venv_dir / "bin" / "postbox-api"
        assert postbox_api.exists(), "postbox-api command not installed"
        assert postbox_api.is_file(), "postbox-api is not a file"


if __name__ == "__main__":
    test_wheel_build()
    print("✓ test_wheel_build passed")

    test_wheel_contains_package()
    print("✓ test_wheel_contains_package passed")

    test_wheel_install_isolated()
    print("✓ test_wheel_install_isolated passed")

    print("\n✓ All packaging tests passed")
