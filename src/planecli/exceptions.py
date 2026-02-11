"""Custom exception hierarchy for PlaneCLI."""

from __future__ import annotations


class PlaneCLIError(Exception):
    """Base exception for all PlaneCLI errors."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = 1,
        hint: str | None = None,
    ) -> None:
        self.message = message
        self.exit_code = exit_code
        self.hint = hint
        super().__init__(message)


class AuthenticationError(PlaneCLIError):
    """Raised when API authentication fails."""

    def __init__(self, message: str = "Authentication failed.") -> None:
        super().__init__(
            message,
            exit_code=2,
            hint="Run 'planecli configure' or set PLANE_API_KEY and PLANE_BASE_URL env vars.",
        )


class ResourceNotFoundError(PlaneCLIError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        super().__init__(
            f"{resource_type} not found: {identifier}",
            exit_code=3,
            hint=f"Use 'planecli {resource_type.lower()} list' to see available resources.",
        )


class APIError(PlaneCLIError):
    """Raised when the Plane API returns an unexpected error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        if status_code:
            detail = f"API error (HTTP {status_code}): {message}"
        else:
            detail = f"API error: {message}"
        super().__init__(detail, exit_code=4)


class ValidationError(PlaneCLIError):
    """Raised for invalid user input."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message, exit_code=5, hint=hint)
