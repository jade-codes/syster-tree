"""Custom exceptions for Systree."""


class SystreeError(Exception):
    """Base exception for all Systree errors."""

    pass


class CliNotFoundError(SystreeError):
    """Raised when the syster CLI binary is not found."""

    def __init__(self, message: str = "Syster CLI not found on PATH") -> None:
        super().__init__(message)


class AnalysisError(SystreeError):
    """Raised when analysis fails."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr
