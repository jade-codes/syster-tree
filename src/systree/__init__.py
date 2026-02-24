"""Systree - Python wrapper for Syster CLI - SysML v2 and KerML analysis."""

from systree.cli import (
    analyze,
    decompile,
    download_cli,
    download_stdlib,
    export_ast,
    export_jsonld,
    export_kpar,
    export_xmi,
    export_yaml,
    find_cli,
    get_cache_dir,
    get_stdlib_path,
    get_symbols,
    import_export,
    import_file,
    import_symbols,
)
from systree.exceptions import AnalysisError, CliNotFoundError, SystreeError
from systree.models import AnalysisResult, FileSymbols, Symbol

__version__ = "0.4.0a2"

# Ensure the correct CLI version is installed on import.
# This is a no-op if the CLI is already present at the right version.
try:
    find_cli()
except CliNotFoundError:
    pass  # cargo not available — user will get a clear error on first use

__all__ = [
    # Analysis functions
    "analyze",
    "get_symbols",
    "export_ast",
    # Export functions
    "export_xmi",
    "export_jsonld",
    "export_kpar",
    "export_yaml",
    # Import functions
    "import_file",
    "import_symbols",
    "import_export",
    "decompile",
    # Stdlib
    "download_stdlib",
    "download_cli",
    "get_stdlib_path",
    "get_cache_dir",
    # Models
    "AnalysisResult",
    "Symbol",
    "FileSymbols",
    # Exceptions
    "SystreeError",
    "CliNotFoundError",
    "AnalysisError",
]
