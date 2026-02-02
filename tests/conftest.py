"""Pytest fixtures for systree tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_sysml_file(tmp_path: Path) -> Path:
    """Create a sample SysML file for testing."""
    sysml_file = tmp_path / "test.sysml"
    sysml_file.write_text(
        """\
package TestPackage {
    part def Vehicle {
        part engine : Engine;
    }
    part def Engine;
}
"""
    )
    return sysml_file


@pytest.fixture
def sample_kerml_file(tmp_path: Path) -> Path:
    """Create a sample KerML file for testing."""
    kerml_file = tmp_path / "test.kerml"
    kerml_file.write_text(
        """\
package TestPackage {
    class TestClass {
        feature x : Integer;
    }
}
"""
    )
    return kerml_file


@pytest.fixture
def sample_directory(tmp_path: Path) -> Path:
    """Create a directory with multiple SysML files."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    (models_dir / "vehicle.sysml").write_text(
        """\
package Vehicles {
    part def Car;
    part def Truck;
}
"""
    )

    (models_dir / "parts.sysml").write_text(
        """\
package Parts {
    part def Wheel;
    part def Engine;
}
"""
    )

    return models_dir
