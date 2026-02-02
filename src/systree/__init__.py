"""Systree - Python wrapper for Syster CLI - SysML v2 and KerML analysis."""

from systree.cli import (
    analyze,
    export_jsonld,
    export_kpar,
    export_xmi,
    get_symbols,
)
from systree.exceptions import AnalysisError, CliNotFoundError, SystreeError
from systree.models import AnalysisResult, FileSymbols, Symbol

__version__ = "0.1.0"

__all__ = [
    # Core functions
    "analyze",
    "get_symbols",
    # Export functions
    "export_xmi",
    "export_jsonld",
    "export_kpar",
    # Models
    "AnalysisResult",
    "Symbol",
    "FileSymbols",
    # Exceptions
    "SystreeError",
    "CliNotFoundError",
    "AnalysisError",
]
