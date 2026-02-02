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

# Pattern to match import output: "✓ Imported N elements, M relationships"
IMPORT_PATTERN = re.compile(r"Imported (\d+) elements?, (\d+) relationships?")


def _find_stdlib() -> Path | None:
    """Find the SysML standard library.

    Searches in order:
    1. SYSML_STDLIB environment variable
    2. User cache directory (~/.cache/systree/sysml.library) - downloaded stdlib
    3. sysml.library in current directory
    4. Relative to this package (for monorepo development)

    Returns:
        Path to stdlib directory, or None if not found.
    """
    import os

    # 1. Environment variable
    env_path = os.environ.get("SYSML_STDLIB")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # 2. User cache directory (downloaded stdlib - preferred)
    cache_dir = Path.home() / ".cache" / "systree" / "sysml.library"
    if cache_dir.exists():
        return cache_dir

    # 3. Current directory
    cwd_path = Path.cwd() / "sysml.library"
    if cwd_path.exists():
        return cwd_path

    # 4. Relative to package (monorepo layout: systree/src/systree/cli.py -> base/sysml.library)
    package_dir = Path(__file__).parent  # systree/src/systree
    monorepo_path = package_dir.parent.parent.parent / "base" / "sysml.library"
    if monorepo_path.exists():
        return monorepo_path

    return None


def download_stdlib(version: str = "2025-12") -> Path:
    """Download the SysML v2 standard library from GitHub.

    Args:
        version: Release version tag (default: "2025-12").

    Returns:
        Path to the downloaded sysml.library directory.

    Raises:
        RuntimeError: If download fails.
    """
    import io
    import urllib.request
    import zipfile

    cache_dir = Path.home() / ".cache" / "systree"
    stdlib_dir = cache_dir / "sysml.library"

    if stdlib_dir.exists():
        return stdlib_dir

    # Download from GitHub release
    url = f"https://github.com/Systems-Modeling/SysML-v2-Release/archive/refs/tags/{version}.zip"

    try:
        print(f"Downloading SysML v2 standard library ({version})...")
        with urllib.request.urlopen(url, timeout=60) as response:
            zip_data = response.read()
    except Exception as e:
        raise RuntimeError(f"Failed to download stdlib from {url}: {e}") from e

    # Extract sysml.library folder
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # Find the sysml.library folder in the archive
            prefix = f"SysML-v2-Release-{version}/sysml.library/"
            for member in zf.namelist():
                if member.startswith(prefix) and not member.endswith("/"):
                    # Extract to cache_dir/sysml.library/...
                    rel_path = member[len(prefix):]
                    target = stdlib_dir / rel_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
        print(f"Installed stdlib to {stdlib_dir}")
    except Exception as e:
        # Clean up partial extraction
        if stdlib_dir.exists():
            import shutil
            shutil.rmtree(stdlib_dir)
        raise RuntimeError(f"Failed to extract stdlib: {e}") from e

    return stdlib_dir


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
        stdlib_path: Custom standard library path (auto-detected if None).

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
    elif stdlib_path is not None:
        cmd.extend(["--stdlib-path", str(stdlib_path)])
    else:
        # Auto-detect or download stdlib
        detected = _find_stdlib()
        if detected is None:
            # Download from GitHub
            detected = download_stdlib()
        cmd.extend(["--stdlib-path", str(detected)])

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


def import_file(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> AnalysisResult:
    """Import and validate an interchange file (XMI, KPAR, or JSON-LD).

    Args:
        path: Path to interchange file to import.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        AnalysisResult with validation results.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If import fails.
    """
    result = _run_cli(
        path,
        args=["--import", "--json"],
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )

    output = result.stdout

    try:
        data = json.loads(output)
        return AnalysisResult(
            file_count=data.get("file_count", 1),
            symbol_count=data.get("symbol_count", 0),
            error_count=data.get("error_count", 0),
            warning_count=data.get("warning_count", 0),
            diagnostics=data.get("diagnostics", []),
        )
    except json.JSONDecodeError:
        pass

    match = SUCCESS_PATTERN.search(output)
    if match:
        return AnalysisResult(
            file_count=int(match.group(1)),
            symbol_count=int(match.group(2)),
        )

    # Try import pattern
    match = IMPORT_PATTERN.search(output)
    if match:
        return AnalysisResult(
            file_count=1,
            symbol_count=int(match.group(1)),  # elements as symbols
        )

    raise AnalysisError(
        f"Could not parse CLI output: {output}",
        stderr=result.stderr,
    )


def import_symbols(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> list[FileSymbols]:
    """Import interchange file and extract symbols.

    Args:
        path: Path to interchange file (XMI, KPAR, or JSON-LD).
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        List of FileSymbols with extracted symbols.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If import fails.
    """
    result = _run_cli(
        path,
        args=["--import", "--export-ast"],
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


def decompile(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> str:
    """Decompile interchange file back to SysML v2 text.

    Args:
        path: Path to interchange file (XMI, KPAR, or JSON-LD).
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        SysML v2 source code as string.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If decompilation fails.
    """
    result = _run_cli(
        path,
        args=["--decompile"],
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )
    return result.stdout


def import_export(
    path: str | Path,
    format: str = "xmi",
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> bytes:
    """Import interchange file and re-export, preserving element IDs.

    This is the direct roundtrip: import XMI/KPAR/JSON-LD into workspace,
    then export back to the specified format. Element IDs are preserved.

    Args:
        path: Path to interchange file (XMI, KPAR, or JSON-LD).
        format: Output format - "xmi", "kpar", or "jsonld" (default: "xmi").
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        Exported model as bytes.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If import or export fails.
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

    cmd.extend(["--import-workspace", "--export", format])
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
            f"Import/export failed with exit code {result.returncode}: {error_message}",
            stderr=error_message,
        )

    return result.stdout
