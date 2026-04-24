"""Custom exceptions for peekxd Linux."""


class peekxdError(Exception):
    """Base exception for all peekxd errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProviderNotAvailableError(peekxdError):
    """Raised when no suitable provider is available for the current environment."""


class ScreenshotError(peekxdError):
    """Raised when screenshot capture fails."""


class InputError(peekxdError):
    """Raised when input simulation fails."""


class InspectionError(peekxdError):
    """Raised when UI inspection fails."""


class VisionError(peekxdError):
    """Raised when vision analysis fails."""


class ConfigurationError(peekxdError):
    """Raised when configuration is invalid or missing."""


class PermissionDeniedError(peekxdError):
    """Raised when required system permissions are missing."""


class WindowError(peekxdError):
    """Raised when window operation fails."""
