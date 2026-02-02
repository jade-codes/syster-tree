"""CLI wrapper for the syster binary."""

import json
import re
import shutil
import subprocess
from pathlib import Path

from systree.exceptions import AnalysisError, CliNotFoundError
from systree.models import AnalysisResult, FileSymbols, Symbol

# Pattern to match the success output: "✓ Analyzed N files: M symbols, W warnings"
SUCCESS_PATTERN = re.compile(r"Analyzed (\d+) files?: (\d+) symbols?")


def find_cli() -> str:
    """Find the syster CLI binary.

    Returns:
        Path to the syster binary.

    Raises:
        CliNotFoundError: If the binary is not found.
    """
    binary = shutil.which("syster")
    if binary is None:
        raise CliNotFoundError(
            "Syster CLI not found on PATH. "
            "Install with: cargo install syster-cli"
        )
    return binary


def _run_cli(
    path: str | Path,
    *,
    args: list[str] | None = None,
    verbose: bool = False,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the syster CLI with given arguments.

    Args:
        path: Path to file or directory to analyze.
        args: Additional CLI arguments.
        verbose: Enable verbose output.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        CompletedProcess with stdout/stderr.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If analysis fails.
    """
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")

    binary = find_cli()

    cmd = [binary]

    if verbose:
        cmd.append("--verbose")

    if not stdlib:
        cmd.append("--no-stdlib")

    if stdlib_path is not None:
        cmd.extend(["--stdlib-path", str(stdlib_path)])

    if args:
        cmd.extend(args)

    cmd.append(str(input_path.resolve()))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        raise CliNotFoundError(f"Failed to execute syster CLI: {e}") from e

    if result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip()
        raise AnalysisError(
            f"Analysis failed with exit code {result.returncode}: {error_message}",
            stderr=result.stderr,
        )

    return result


def analyze(
    path: str | Path,
    *,
    verbose: bool = False,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> AnalysisResult:
    """Analyze a SysML v2 or KerML file or directory.

    Args:
        path: Path to file or directory to analyze.
        verbose: Enable verbose output.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        AnalysisResult with file_count, symbol_count, and diagnostics.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If analysis fails.
    """
    result = _run_cli(
        path,
        args=["--json"],
        verbose=verbose,
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )

    output = result.stdout

    # Try to parse JSON output first
    try:
        data = json.loads(output)
        return AnalysisResult(
            file_count=data.get("file_count", 0),
            symbol_count=data.get("symbol_count", 0),
            error_count=data.get("error_count", 0),
            warning_count=data.get("warning_count", 0),
            diagnostics=data.get("diagnostics", []),
        )
    except json.JSONDecodeError:
        pass

    # Fall back to regex parsing
    match = SUCCESS_PATTERN.search(output)
    if match:
        file_count = int(match.group(1))
        symbol_count = int(match.group(2))
        return AnalysisResult(file_count=file_count, symbol_count=symbol_count)

    raise AnalysisError(
        f"Could not parse CLI output: {output}",
        stderr=result.stderr,
    )


def get_symbols(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> list[FileSymbols]:
    """Extract symbols from SysML v2 or KerML files.

    Args:
        path: Path to file or directory to analyze.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        List of FileSymbols, each containing a file path and its symbols.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If analysis fails.
    """
    result = _run_cli(
        path,
        args=["--export-ast"],
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AnalysisError(
            f"Failed to parse AST JSON: {e}",
            stderr=result.stderr,
        ) from e

    file_symbols_list: list[FileSymbols] = []

    files = data if isinstance(data, list) else data.get("files", [data])
    for file_data in files:
        file_path = file_data.get("file", file_data.get("path", "unknown"))
        symbols: list[Symbol] = []

        for sym in file_data.get("symbols", []):
            symbols.append(
                Symbol(
                    name=sym.get("name", ""),
                    qualified_name=sym.get("qualified_name", sym.get("name", "")),
                    kind=sym.get("kind", "Unknown"),
                    file=file_path,
                    start_line=sym.get("start_line"),
                    start_col=sym.get("start_col"),
                    end_line=sym.get("end_line"),
                    end_col=sym.get("end_col"),
                    supertypes=sym.get("supertypes", []),
                )
            )

        file_symbols_list.append(FileSymbols(path=file_path, symbols=symbols))

    return file_symbols_list


def export_xmi(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> str:
    """Export SysML/KerML model to XMI format.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        XMI XML string.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If export fails.
    """
    result = _run_cli(
        path,
        args=["--export", "xmi"],
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )
    return result.stdout


def export_jsonld(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> list | dict:
    """Export SysML/KerML model to JSON-LD format.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        JSON-LD data (list of elements or dict with @graph).

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If export fails.
    """
    result = _run_cli(
        path,
        args=["--export", "json-ld"],
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AnalysisError(
            f"Failed to parse JSON-LD: {e}",
            stderr=result.stderr,
        ) from e


def export_kpar(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> bytes:
    """Export SysML/KerML model to KPAR format.

    KPAR (Kernel Package Archive) is a ZIP file containing XMI and metadata.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        KPAR archive as bytes (ZIP format).

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If export fails.
    """
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")

    binary = find_cli()

    cmd = [binary]

    if not stdlib:
        cmd.append("--no-stdlib")

    if stdlib_path is not None:
        cmd.extend(["--stdlib-path", str(stdlib_path)])

    cmd.extend(["--export", "kpar"])
    cmd.append(str(input_path.resolve()))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )
    except OSError as e:
        raise CliNotFoundError(f"Failed to execute syster CLI: {e}") from e

    if result.returncode != 0:
        error_message = result.stderr.decode(errors="replace").strip()
        raise AnalysisError(
            f"Export failed with exit code {result.returncode}: {error_message}",
            stderr=error_message,
        )

    return result.stdout
