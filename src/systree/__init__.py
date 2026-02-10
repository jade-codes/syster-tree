"""Systree - Python wrapper for Syster CLI - SysML v2 and KerML analysis."""

from systree.cli import (
    analyze,
    decompile,
    download_stdlib,
    export_ast,
    export_jsonld,
    export_kpar,
    export_xmi,
    export_yaml,
    get_cache_dir,
    get_stdlib_path,
    get_symbols,
    import_export,
    import_file,
    import_symbols,
)
from systree.exceptions import AnalysisError, CliNotFoundError, SystreeError
from systree.models import AnalysisResult, FileSymbols, Symbol

__version__ = "0.3.2"

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
