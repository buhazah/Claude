"""Error taxonomy.

Callers should be able to decide what to do from the *type* alone: retry the
same provider, fall back to the next one, ask the user, or give up.
"""

from __future__ import annotations


class JarvisError(Exception):
    """Base for every error the kernel raises."""

    status_code = 500


class ConfigurationError(JarvisError):
    """The system is misconfigured — never retryable."""

    status_code = 500


class NotFoundError(JarvisError):
    status_code = 404


class ProviderError(JarvisError):
    """An LLM provider failed. Carries whether falling back is worthwhile."""

    status_code = 502

    def __init__(self, message: str, *, provider: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class ProviderUnavailableError(ProviderError):
    """Provider is not configured or its circuit is open."""


class AllProvidersFailedError(JarvisError):
    """Every candidate in the fallback chain failed."""

    status_code = 503

    def __init__(self, message: str, *, failures: dict[str, str]) -> None:
        super().__init__(message)
        self.failures = failures


class PermissionDeniedError(JarvisError):
    """A tool call was refused by the permission system."""

    status_code = 403


class ApprovalRequiredError(JarvisError):
    """A dangerous tool needs explicit human approval before it can run."""

    status_code = 409

    def __init__(self, message: str, *, tool: str) -> None:
        super().__init__(message)
        self.tool = tool
