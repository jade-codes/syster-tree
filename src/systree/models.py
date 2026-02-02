"""Data models for Systree analysis results."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalysisResult:
    """Result of analyzing SysML v2 or KerML files.

    Attributes:
        file_count: Number of files that were analyzed.
        symbol_count: Number of symbols found across all files.
        error_count: Number of errors found.
        warning_count: Number of warnings found.
        diagnostics: List of diagnostic messages.
    """

    file_count: int
    symbol_count: int
    error_count: int = 0
    warning_count: int = 0
    diagnostics: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Symbol:
    """A symbol extracted from SysML/KerML source.

    Attributes:
        name: Simple name of the symbol.
        qualified_name: Fully qualified name (e.g., "Package::Class").
        kind: Symbol kind (e.g., "Package", "PartDef", "PartUsage").
        file: Source file path.
        start_line: Starting line number (1-based).
        start_col: Starting column number (1-based).
        end_line: Ending line number.
        end_col: Ending column number.
        supertypes: List of supertype names.
    """

    name: str
    qualified_name: str
    kind: str
    file: str | None = None
    start_line: int | None = None
    start_col: int | None = None
    end_line: int | None = None
    end_col: int | None = None
    supertypes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FileSymbols:
    """Symbols from a single file.

    Attributes:
        path: File path.
        symbols: List of symbols in the file.
    """

    path: str
    symbols: list[Symbol]
