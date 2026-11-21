"""Exceptions understood by Securo's plugin runner."""


class NeedsAuth(Exception):
    """Credentials or API access must be fixed by the user."""

    def __init__(self, message: str, *, code: str = "credentials_invalid") -> None:
        super().__init__(message)
        self.code = code


class ApiTransient(Exception):
    """Temporary T-Bank or network failure."""
