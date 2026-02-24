"""CLI wrapper for the syster binary."""

import json
import re
import shutil
import subprocess
import warnings
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

    # 2. User cache directory (downloaded stdlib)
    cache_dir = Path.home() / ".cache" / "systree" / "sysml.library"
    if cache_dir.exists():
        return cache_dir

    return None


def get_stdlib_path() -> Path:
    """Get the path to the SysML standard library.

    Returns the path to the stdlib, downloading it if necessary.
    Use this to see which stdlib path will be used by default.

    Returns:
        Path to the sysml.library directory.

    Example:
        >>> from systree import get_stdlib_path
        >>> print(get_stdlib_path())
        /home/user/.cache/systree/sysml.library
    """
    detected = _find_stdlib()
    if detected is None:
        detected = download_stdlib()
    return detected


def get_cache_dir() -> Path:
    """Get the systree cache directory path.

    This is where the stdlib is downloaded to: ~/.cache/systree/

    Returns:
        Path to the cache directory.
    """
    return Path.home() / ".cache" / "systree"


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


# CLI version that this Python package is aligned with
CLI_VERSION = "0.4.0-alpha"


def _cli_cache_dir() -> Path:
    """Get the directory where the CLI binary is installed."""
    return Path.home() / ".cache" / "systree" / "bin"


def _cli_cache_path() -> Path:
    """Get the path where the CLI binary is cached."""
    return _cli_cache_dir() / "syster"


def download_cli(version: str | None = None) -> Path:
    """Install the syster CLI from crates.io using cargo.

    Args:
        version: CLI version to install (default: version aligned with this package).

    Returns:
        Path to the installed binary.

    Raises:
        RuntimeError: If cargo is not available or install fails.
    """
    if version is None:
        version = CLI_VERSION

    cache_bin = _cli_cache_dir()
    binary_path = _cli_cache_path()

    # If already cached, check version matches
    if binary_path.exists():
        cached_version = _get_cli_version(str(binary_path))
        if cached_version == version:
            return binary_path
        print(f"Cached CLI version {cached_version} != {version}, reinstalling...")

    cargo = shutil.which("cargo")
    if cargo is None:
        raise RuntimeError(
            "cargo not found. Install Rust from https://rustup.rs/ "
            "or install the CLI manually: cargo install syster-cli"
        )

    cache_bin.mkdir(parents=True, exist_ok=True)

    print(f"Installing syster-cli@{version} from crates.io...")
    try:
        result = subprocess.run(
            [cargo, "install", f"syster-cli@{version}", "--root", str(cache_bin.parent)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        raise RuntimeError(f"Failed to run cargo: {e}") from e

    if result.returncode != 0:
        raise RuntimeError(
            f"cargo install failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )

    # cargo install --root puts binaries in <root>/bin/
    installed = cache_bin / "syster"
    if not installed.exists():
        raise RuntimeError(
            f"cargo install succeeded but binary not found at {installed}"
        )

    print(f"Installed syster CLI to {installed}")
    return installed


def _get_cli_version(binary: str) -> str | None:
    """Get the version string from a syster binary.

    Returns the version (e.g. '0.4.0-alpha') or None if it can't be determined.
    """
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            # Output is like "syster-cli 0.4.0-alpha"
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                return parts[-1]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def find_cli() -> str:
    """Find the syster CLI binary at the correct version.

    Searches for an existing binary on PATH or in cache, and verifies
    it matches CLI_VERSION. If the version is wrong or no binary is found,
    installs the correct version from crates.io via cargo.

    Returns:
        Path to the syster binary at the correct version.

    Raises:
        CliNotFoundError: If the binary cannot be found or installed.
    """
    # 1. Check PATH
    binary = shutil.which("syster")
    if binary is not None:
        version = _get_cli_version(binary)
        if version == CLI_VERSION:
            return binary

    # 2. Check cache
    cached = _cli_cache_path()
    if cached.exists():
        version = _get_cli_version(str(cached))
        if version == CLI_VERSION:
            return str(cached)

    # 3. Install correct version from crates.io
    try:
        downloaded = download_cli()
        return str(downloaded)
    except RuntimeError as e:
        raise CliNotFoundError(
            f"Syster CLI {CLI_VERSION} not found and auto-install failed: {e}"
        ) from e


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

    if result.returncode not in (0, 2):
        error_message = result.stderr.strip() or result.stdout.strip()
        raise AnalysisError(
            f"Analysis failed with exit code {result.returncode}: {error_message}",
            stderr=result.stderr,
        )

    if result.returncode == 2:
        warnings.warn(
            f"CLI completed with warnings: {result.stderr.strip()}",
            stacklevel=3,
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


def export_ast(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
) -> dict:
    """Export raw AST (Abstract Syntax Tree) as JSON.

    This returns the raw JSON output from the CLI's --export-ast flag.
    For typed symbol objects, use get_symbols() instead.

    Args:
        path: Path to file or directory to analyze.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.

    Returns:
        Dict with "files" key containing list of file data with symbols.

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
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AnalysisError(
            f"Failed to parse AST JSON: {e}",
            stderr=result.stderr,
        ) from e


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
    self_contained: bool = False,
) -> str:
    """Export SysML/KerML model to XMI format.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.
        self_contained: Include standard library in export (default: False).

    Returns:
        XMI XML string.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If export fails.
    """
    args = ["--export", "xmi"]
    if self_contained:
        args.append("--self-contained")
    result = _run_cli(
        path,
        args=args,
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )
    return result.stdout


def export_jsonld(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
    self_contained: bool = False,
) -> list | dict:
    """Export SysML/KerML model to JSON-LD format.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.
        self_contained: Include standard library in export (default: False).

    Returns:
        JSON-LD data (list of elements or dict with @graph).

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If export fails.
    """
    args = ["--export", "json-ld"]
    if self_contained:
        args.append("--self-contained")
    result = _run_cli(
        path,
        args=args,
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
    self_contained: bool = False,
) -> bytes:
    """Export SysML/KerML model to KPAR format.

    KPAR (Kernel Package Archive) is a ZIP file containing XMI and metadata.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.
        self_contained: Include standard library in export (default: False).

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
    if self_contained:
        cmd.append("--self-contained")
    cmd.append(str(input_path.resolve()))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )
    except OSError as e:
        raise CliNotFoundError(f"Failed to execute syster CLI: {e}") from e

    if result.returncode not in (0, 2):
        error_message = result.stderr.decode(errors="replace").strip()
        raise AnalysisError(
            f"Export failed with exit code {result.returncode}: {error_message}",
            stderr=error_message,
        )

    if result.returncode == 2:
        warnings.warn(
            f"CLI completed with warnings: {result.stderr.decode(errors='replace').strip()}",
            stacklevel=2,
        )

    return result.stdout


def export_yaml(
    path: str | Path,
    *,
    stdlib: bool = True,
    stdlib_path: str | Path | None = None,
    self_contained: bool = False,
) -> str:
    """Export SysML/KerML model to YAML format.

    Args:
        path: Path to file or directory to export.
        stdlib: Load standard library (default: True).
        stdlib_path: Custom standard library path.
        self_contained: Include standard library in export (default: False).

    Returns:
        YAML string.

    Raises:
        FileNotFoundError: If the input path doesn't exist.
        CliNotFoundError: If the syster CLI is not found.
        AnalysisError: If export fails.
    """
    args = ["--export", "yaml"]
    if self_contained:
        args.append("--self-contained")
    result = _run_cli(
        path,
        args=args,
        stdlib=stdlib,
        stdlib_path=stdlib_path,
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
    input_path = Path(path)
    result = _run_cli(
        path,
        args=["--decompile"],
        stdlib=stdlib,
        stdlib_path=stdlib_path,
    )

    # CLI 0.4.0+ writes decompiled SysML to a file alongside the input,
    # e.g. model.xmi -> model.sysml. Read that file if it exists.
    output_sysml = input_path.with_suffix(".sysml")
    if output_sysml.exists():
        return output_sysml.read_text()

    # Fallback: return stdout (older CLI versions may print to stdout)
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

    if result.returncode not in (0, 2):
        error_message = result.stderr.decode(errors="replace").strip()
        raise AnalysisError(
            f"Import/export failed with exit code {result.returncode}: {error_message}",
            stderr=error_message,
        )

    if result.returncode == 2:
        warnings.warn(
            f"CLI completed with warnings: {result.stderr.decode(errors='replace').strip()}",
            stacklevel=2,
        )

    return result.stdout
