"""Tests for the CLI wrapper."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from systree import AnalysisResult, FileSymbols, Symbol, analyze
from systree.cli import (
    SUCCESS_PATTERN,
    export_jsonld,
    export_kpar,
    export_xmi,
    find_cli,
    get_symbols,
)
from systree.exceptions import AnalysisError, CliNotFoundError


class TestSuccessPattern:
    """Tests for the success output pattern."""

    def test_matches_single_file(self) -> None:
        output = "✓ Analyzed 1 file: 42 symbols, 0 warnings"
        match = SUCCESS_PATTERN.search(output)
        assert match is not None
        assert match.group(1) == "1"
        assert match.group(2) == "42"

    def test_matches_multiple_files(self) -> None:
        output = "✓ Analyzed 10 files: 123 symbols, 0 warnings"
        match = SUCCESS_PATTERN.search(output)
        assert match is not None
        assert match.group(1) == "10"
        assert match.group(2) == "123"

    def test_matches_large_numbers(self) -> None:
        output = "✓ Analyzed 999 files: 12345 symbols, 5 warnings"
        match = SUCCESS_PATTERN.search(output)
        assert match is not None
        assert match.group(1) == "999"
        assert match.group(2) == "12345"


class TestFindCli:
    """Tests for CLI binary discovery."""

    def test_find_cli_success(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/syster"):
            assert find_cli() == "/usr/bin/syster"

    def test_find_cli_not_found(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(CliNotFoundError):
                find_cli()


class TestAnalyze:
    """Tests for the analyze function."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            analyze("/nonexistent/path/model.sysml")

    def test_cli_not_found(self, sample_sysml_file: Path) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(CliNotFoundError):
                analyze(sample_sysml_file)

    def test_successful_analysis(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "✓ Analyzed 1 file: 5 symbols, 0 warnings"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = analyze(sample_sysml_file)
            assert isinstance(result, AnalysisResult)
            assert result.file_count == 1
            assert result.symbol_count == 5

    def test_analysis_with_options(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "✓ Analyzed 1 file: 5 symbols, 0 warnings"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            analyze(
                sample_sysml_file,
                verbose=True,
                stdlib=False,
                stdlib_path="/custom/stdlib",
            )

            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "--verbose" in cmd
            assert "--no-stdlib" in cmd
            assert "--stdlib-path" in cmd
            assert "/custom/stdlib" in cmd

    def test_analysis_failure(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Parse error at line 1"

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(AnalysisError) as exc_info:
                analyze(sample_sysml_file)
            assert "Parse error" in str(exc_info.value)

    def test_unparseable_output(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Some unexpected output"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(AnalysisError) as exc_info:
                analyze(sample_sysml_file)
            assert "Could not parse" in str(exc_info.value)


class TestAnalysisResult:
    """Tests for the AnalysisResult dataclass."""

    def test_creation(self) -> None:
        result = AnalysisResult(file_count=5, symbol_count=100)
        assert result.file_count == 5
        assert result.symbol_count == 100

    def test_creation_with_diagnostics(self) -> None:
        diags = [{"file": "test.sysml", "line": 1, "message": "error"}]
        result = AnalysisResult(
            file_count=1,
            symbol_count=5,
            error_count=1,
            warning_count=2,
            diagnostics=diags,
        )
        assert result.error_count == 1
        assert result.warning_count == 2
        assert result.diagnostics == diags

    def test_immutable(self) -> None:
        result = AnalysisResult(file_count=5, symbol_count=100)
        with pytest.raises(AttributeError):
            result.file_count = 10  # type: ignore[misc]

    def test_repr(self) -> None:
        result = AnalysisResult(file_count=5, symbol_count=100)
        assert "file_count=5" in repr(result)
        assert "symbol_count=100" in repr(result)


class TestSymbol:
    """Tests for the Symbol dataclass."""

    def test_creation(self) -> None:
        sym = Symbol(
            name="Car",
            qualified_name="Vehicle::Car",
            kind="PartDef",
        )
        assert sym.name == "Car"
        assert sym.qualified_name == "Vehicle::Car"
        assert sym.kind == "PartDef"

    def test_creation_with_location(self) -> None:
        sym = Symbol(
            name="Engine",
            qualified_name="Vehicle::Engine",
            kind="PartDef",
            file="/path/to/model.sysml",
            start_line=10,
            start_col=5,
            end_line=10,
            end_col=11,
            supertypes=["Parts::Part"],
        )
        assert sym.file == "/path/to/model.sysml"
        assert sym.start_line == 10
        assert sym.start_col == 5
        assert sym.supertypes == ["Parts::Part"]

    def test_immutable(self) -> None:
        sym = Symbol(name="Test", qualified_name="Test", kind="Package")
        with pytest.raises(AttributeError):
            sym.name = "Changed"  # type: ignore[misc]


class TestFileSymbols:
    """Tests for the FileSymbols dataclass."""

    def test_creation(self) -> None:
        symbols = [
            Symbol(name="A", qualified_name="A", kind="Package"),
            Symbol(name="B", qualified_name="A::B", kind="PartDef"),
        ]
        fs = FileSymbols(path="/path/to/file.sysml", symbols=symbols)
        assert fs.path == "/path/to/file.sysml"
        assert len(fs.symbols) == 2


class TestGetSymbols:
    """Tests for the get_symbols function."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            get_symbols("/nonexistent/path/model.sysml")

    def test_successful_extraction(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "files": [{
                "path": str(sample_sysml_file),
                "symbols": [
                    {
                        "name": "TestPackage",
                        "qualified_name": "TestPackage",
                        "kind": "Package",
                        "start_line": 1,
                        "start_col": 9,
                    },
                    {
                        "name": "Vehicle",
                        "qualified_name": "TestPackage::Vehicle",
                        "kind": "PartDef",
                        "start_line": 2,
                        "start_col": 14,
                        "supertypes": ["Parts::Part"],
                    },
                ],
            }]
        })
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = get_symbols(sample_sysml_file)

            assert len(result) == 1
            assert isinstance(result[0], FileSymbols)
            assert len(result[0].symbols) == 2

            pkg = result[0].symbols[0]
            assert pkg.name == "TestPackage"
            assert pkg.kind == "Package"
            assert pkg.start_line == 1

            part = result[0].symbols[1]
            assert part.qualified_name == "TestPackage::Vehicle"
            assert part.supertypes == ["Parts::Part"]

    def test_invalid_json(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(AnalysisError) as exc_info:
                get_symbols(sample_sysml_file)
            assert "Failed to parse AST JSON" in str(exc_info.value)


class TestExportXmi:
    """Tests for the export_xmi function."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            export_xmi("/nonexistent/path/model.sysml")

    def test_successful_export(self, sample_sysml_file: Path) -> None:
        xmi_output = '<?xml version="1.0"?><xmi:XMI></xmi:XMI>'
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = xmi_output
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = export_xmi(sample_sysml_file)

            assert result == xmi_output
            cmd = mock_run.call_args[0][0]
            assert "--export" in cmd
            assert "xmi" in cmd


class TestExportJsonld:
    """Tests for the export_jsonld function."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            export_jsonld("/nonexistent/path/model.sysml")

    def test_successful_export_dict(self, sample_sysml_file: Path) -> None:
        jsonld_data = {"@context": "https://sysml.org", "@graph": []}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(jsonld_data)
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = export_jsonld(sample_sysml_file)

            assert result == jsonld_data
            cmd = mock_run.call_args[0][0]
            assert "--export" in cmd
            assert "json-ld" in cmd

    def test_successful_export_list(self, sample_sysml_file: Path) -> None:
        jsonld_data = [{"@type": "Package", "name": "Test"}]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(jsonld_data)
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = export_jsonld(sample_sysml_file)
            assert result == jsonld_data
            assert isinstance(result, list)

    def test_invalid_json(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(AnalysisError) as exc_info:
                export_jsonld(sample_sysml_file)
            assert "Failed to parse JSON-LD" in str(exc_info.value)


class TestExportKpar:
    """Tests for the export_kpar function."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            export_kpar("/nonexistent/path/model.sysml")

    def test_successful_export(self, sample_sysml_file: Path) -> None:
        # KPAR is a ZIP file, so we mock binary output
        kpar_data = b"PK\x03\x04..."  # ZIP magic bytes
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = kpar_data
        mock_result.stderr = b""

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = export_kpar(sample_sysml_file)

            assert result == kpar_data
            assert isinstance(result, bytes)
            cmd = mock_run.call_args[0][0]
            assert "--export" in cmd
            assert "kpar" in cmd

    def test_export_failure(self, sample_sysml_file: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"Export error"

        with (
            patch("shutil.which", return_value="/usr/bin/syster"),
            patch("subprocess.run", return_value=mock_result),
        ):
            with pytest.raises(AnalysisError) as exc_info:
                export_kpar(sample_sysml_file)
            assert "Export failed" in str(exc_info.value)


@pytest.mark.integration
class TestIntegration:
    """Integration tests that require the actual CLI binary.

    Run with: pytest -m integration
    """

    @pytest.fixture
    def cli_available(self) -> bool:
        """Check if the CLI is available."""
        import shutil

        return shutil.which("syster") is not None

    def test_real_analysis(
        self, cli_available: bool, sample_sysml_file: Path
    ) -> None:
        if not cli_available:
            pytest.skip("Syster CLI not available")

        result = analyze(sample_sysml_file, stdlib=False)
        assert result.file_count >= 1
        assert result.symbol_count >= 0

    def test_real_get_symbols(
        self, cli_available: bool, sample_sysml_file: Path
    ) -> None:
        if not cli_available:
            pytest.skip("Syster CLI not available")

        result = get_symbols(sample_sysml_file, stdlib=False)
        assert len(result) >= 1
        assert isinstance(result[0], FileSymbols)
        # Should have TestPackage, Vehicle, Engine at minimum
        assert len(result[0].symbols) >= 1

    def test_real_export_xmi(
        self, cli_available: bool, sample_sysml_file: Path
    ) -> None:
        if not cli_available:
            pytest.skip("Syster CLI not available")

        result = export_xmi(sample_sysml_file, stdlib=False)
        assert isinstance(result, str)
        assert "<?xml" in result or "<xmi:" in result

    def test_real_export_jsonld(
        self, cli_available: bool, sample_sysml_file: Path
    ) -> None:
        if not cli_available:
            pytest.skip("Syster CLI not available")

        result = export_jsonld(sample_sysml_file, stdlib=False)
        assert isinstance(result, (list, dict))

    def test_real_export_kpar(
        self, cli_available: bool, sample_sysml_file: Path
    ) -> None:
        if not cli_available:
            pytest.skip("Syster CLI not available")

        result = export_kpar(sample_sysml_file, stdlib=False)
        assert isinstance(result, bytes)
        # KPAR is a ZIP file, should start with PK magic bytes
        assert result[:2] == b"PK"


@pytest.mark.integration
class TestOutputFormats:
    """Test that output formats contain expected content for a known model."""

    @pytest.fixture
    def vehicle_model(self, tmp_path: Path) -> Path:
        """Create a vehicle model for format testing."""
        model = tmp_path / "vehicle.sysml"
        model.write_text("""\
package VehicleModel {
    doc /* A simple vehicle model for testing */

    part def Vehicle {
        part engine : Engine;
        part wheels : Wheel[4];
    }

    part def Engine {
        attribute horsepower : Integer;
    }

    part def Wheel;
}
""")
        return model

    @pytest.fixture
    def cli_available(self) -> bool:
        import shutil
        return shutil.which("syster") is not None

    def test_analyze_vehicle_model(
        self, cli_available: bool, vehicle_model: Path
    ) -> None:
        """Test analyze returns correct data for vehicle model."""
        if not cli_available:
            pytest.skip("Syster CLI not available")

        result = analyze(vehicle_model, stdlib=False)

        # Verify exact counts
        assert result.file_count == 1

        # Verify diagnostics structure if present
        for diag in result.diagnostics:
            assert "message" in diag
            assert "line" in diag or "severity" in diag

    def test_get_symbols_vehicle_model(
        self, cli_available: bool, vehicle_model: Path
    ) -> None:
        """Test get_symbols extracts all symbols with correct metadata."""
        if not cli_available:
            pytest.skip("Syster CLI not available")

        file_symbols = get_symbols(vehicle_model, stdlib=False)

        assert len(file_symbols) == 1
        fs = file_symbols[0]
        assert "vehicle.sysml" in fs.path

        # Build lookup by name
        symbols_by_name = {s.name: s for s in fs.symbols}

        # Verify VehicleModel package
        assert "VehicleModel" in symbols_by_name
        pkg = symbols_by_name["VehicleModel"]
        assert pkg.kind == "Package"
        assert pkg.qualified_name == "VehicleModel"
        assert pkg.start_line == 1
        assert pkg.start_col == 9  # "package VehicleModel" - V starts at col 9

        # Verify Vehicle part def
        assert "Vehicle" in symbols_by_name
        vehicle = symbols_by_name["Vehicle"]
        assert vehicle.kind == "PartDef"
        assert vehicle.qualified_name == "VehicleModel::Vehicle"
        assert vehicle.start_line == 4  # Line 4: "    part def Vehicle {"

        # Verify Engine part def
        assert "Engine" in symbols_by_name
        engine = symbols_by_name["Engine"]
        assert engine.kind == "PartDef"
        assert engine.qualified_name == "VehicleModel::Engine"
        assert engine.start_line == 9  # Line 9: "    part def Engine {"

        # Verify Wheel part def
        assert "Wheel" in symbols_by_name
        wheel = symbols_by_name["Wheel"]
        assert wheel.kind == "PartDef"
        assert wheel.qualified_name == "VehicleModel::Wheel"
        assert wheel.start_line == 13  # Line 13: "    part def Wheel;"

        # Verify nested parts (engine usage inside Vehicle)
        assert "engine" in symbols_by_name
        engine_usage = symbols_by_name["engine"]
        assert engine_usage.kind == "PartUsage"
        assert engine_usage.qualified_name == "VehicleModel::Vehicle::engine"
        assert engine_usage.start_line == 5

        # Verify wheels usage
        assert "wheels" in symbols_by_name
        wheels = symbols_by_name["wheels"]
        assert wheels.kind == "PartUsage"
        assert wheels.qualified_name == "VehicleModel::Vehicle::wheels"
        assert wheels.start_line == 6

        # Verify horsepower attribute
        assert "horsepower" in symbols_by_name
        hp = symbols_by_name["horsepower"]
        assert hp.kind == "AttributeUsage"
        assert hp.qualified_name == "VehicleModel::Engine::horsepower"
        assert hp.start_line == 10

    def test_export_xmi_vehicle_model(
        self, cli_available: bool, vehicle_model: Path
    ) -> None:
        """Test XMI export contains expected XML structure and data."""
        if not cli_available:
            pytest.skip("Syster CLI not available")

        xmi = export_xmi(vehicle_model, stdlib=False)

        # Check XML declaration and namespaces
        assert '<?xml version="1.0"' in xmi
        assert "xmi:XMI" in xmi
        assert "xmlns:xmi" in xmi

        # Check all model elements are present with correct structure
        assert 'name="VehicleModel"' in xmi
        assert 'name="Vehicle"' in xmi
        assert 'name="Engine"' in xmi
        assert 'name="Wheel"' in xmi
        assert 'name="engine"' in xmi
        assert 'name="wheels"' in xmi
        assert 'name="horsepower"' in xmi

        # Check qualified names
        assert 'qualifiedName="VehicleModel"' in xmi
        assert 'qualifiedName="VehicleModel::Vehicle"' in xmi
        assert 'qualifiedName="VehicleModel::Engine"' in xmi

    def test_export_jsonld_vehicle_model(
        self, cli_available: bool, vehicle_model: Path
    ) -> None:
        """Test JSON-LD export contains expected structure and data."""
        if not cli_available:
            pytest.skip("Syster CLI not available")

        jsonld = export_jsonld(vehicle_model, stdlib=False)

        # JSON-LD can be list or dict with @graph
        elements = jsonld if isinstance(jsonld, list) else jsonld.get("@graph", [jsonld])

        # Build lookup by name
        by_name = {e["name"]: e for e in elements if isinstance(e, dict) and "name" in e}

        # Verify VehicleModel package
        assert "VehicleModel" in by_name
        pkg = by_name["VehicleModel"]
        assert pkg["@type"] == "Package"

        # Verify Vehicle part def
        assert "Vehicle" in by_name
        vehicle = by_name["Vehicle"]
        assert vehicle["@type"] == "PartDefinition"

        # Verify Engine part def
        assert "Engine" in by_name
        engine = by_name["Engine"]
        assert engine["@type"] == "PartDefinition"

        # Verify Wheel part def
        assert "Wheel" in by_name
        wheel = by_name["Wheel"]
        assert wheel["@type"] == "PartDefinition"

        # Verify part usages
        assert "engine" in by_name
        engine_usage = by_name["engine"]
        assert engine_usage["@type"] == "PartUsage"

        assert "wheels" in by_name
        wheels = by_name["wheels"]
        assert wheels["@type"] == "PartUsage"

        # Verify attribute
        assert "horsepower" in by_name
        hp = by_name["horsepower"]
        assert hp["@type"] == "AttributeUsage"

        # Verify relationships exist (owner references)
        assert "owner" in engine_usage or "owningMembership" in engine_usage

    def test_export_kpar_vehicle_model(
        self, cli_available: bool, vehicle_model: Path
    ) -> None:
        """Test KPAR export produces valid ZIP with expected contents."""
        if not cli_available:
            pytest.skip("Syster CLI not available")

        import io
        import zipfile

        kpar_bytes = export_kpar(vehicle_model, stdlib=False)

        # Verify it's a valid ZIP
        assert kpar_bytes[:2] == b"PK"

        # Open and inspect ZIP contents
        with zipfile.ZipFile(io.BytesIO(kpar_bytes), "r") as zf:
            names = zf.namelist()

            # KPAR should contain metadata and model files
            assert len(names) >= 1

            # Find and verify XMI content
            xmi_files = [n for n in names if n.endswith(".xmi")]
            assert len(xmi_files) >= 1, f"No XMI files in KPAR: {names}"

            for xmi_name in xmi_files:
                content = zf.read(xmi_name).decode("utf-8")

                # Verify model data in XMI
                assert 'name="VehicleModel"' in content
                assert 'name="Vehicle"' in content
                assert 'name="Engine"' in content
                assert 'name="Wheel"' in content

            # Check for META-INF if present
            meta_files = [n for n in names if "META" in n.upper()]
            if meta_files:
                # Verify manifest structure
                manifest = next((n for n in meta_files if "MANIFEST" in n.upper()), None)
                if manifest:
                    manifest_content = zf.read(manifest).decode("utf-8")
                    assert len(manifest_content) > 0

    def test_all_formats_consistent(
        self, cli_available: bool, vehicle_model: Path
    ) -> None:
        """Test that all export formats represent the same model with matching data."""
        if not cli_available:
            pytest.skip("Syster CLI not available")

        import io
        import zipfile

        # Get all formats
        symbols = get_symbols(vehicle_model, stdlib=False)
        xmi = export_xmi(vehicle_model, stdlib=False)
        jsonld = export_jsonld(vehicle_model, stdlib=False)
        kpar = export_kpar(vehicle_model, stdlib=False)

        # Expected elements
        expected_names = {"VehicleModel", "Vehicle", "Engine", "Wheel", "engine", "wheels", "horsepower"}

        # Verify symbols has all elements
        symbol_names = {s.name for s in symbols[0].symbols}
        for name in expected_names:
            assert name in symbol_names, f"{name} missing from symbols"

        # Verify XMI has all elements
        for name in expected_names:
            assert f'name="{name}"' in xmi, f'{name} missing from XMI'

        # Verify JSON-LD has all elements
        elements = jsonld if isinstance(jsonld, list) else jsonld.get("@graph", [])
        jsonld_names = {e.get("name") for e in elements if isinstance(e, dict)}
        for name in expected_names:
            assert name in jsonld_names, f"{name} missing from JSON-LD"

        # Verify KPAR XMI has all elements
        with zipfile.ZipFile(io.BytesIO(kpar), "r") as zf:
            for zname in zf.namelist():
                if zname.endswith(".xmi"):
                    content = zf.read(zname).decode("utf-8")
                    for name in expected_names:
                        assert f'name="{name}"' in content, f"{name} missing from KPAR XMI"

        # Verify symbol metadata consistency between formats
        symbols_by_name = {s.name: s for s in symbols[0].symbols}

        # Vehicle should be PartDef/PartDefinition in all formats
        vehicle_sym = symbols_by_name["Vehicle"]
        assert vehicle_sym.kind == "PartDef"
        assert "PartDefinition" in xmi or "PartDef" in xmi

        elements_by_name = {e["name"]: e for e in elements if isinstance(e, dict) and "name" in e}
        assert elements_by_name["Vehicle"]["@type"] == "PartDefinition"
