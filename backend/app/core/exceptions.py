"""
Domain exceptions, per ODD Table 1.3 ("Domain exceptions and responses").

Services raise these; a single FastAPI exception handler (registered in
main.py) turns each into the matching HTTP status code and rolls back the
transaction (NFR-03). Unexpected errors are logged and returned as a
general 500 without internal details.
"""


class DomainError(Exception):
    """Base class for every domain exception."""

    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class AuthenticationError(DomainError):
    """401 — wrong password, inactive user, or missing/expired/invalid token."""

    status_code = 401
    default_message = "Invalid credentials or session expired."


class PermissionDeniedError(DomainError):
    """403 — the role of the user may not use this route or record."""

    status_code = 403
    default_message = "You do not have permission to perform this action."


class NotFoundError(DomainError):
    """404 — a product, batch, order, user, or other record does not exist."""

    status_code = 404
    default_message = "The requested resource was not found."


class ValidationFailedError(DomainError):
    """422 — input is incomplete or invalid."""

    status_code = 422
    default_message = "The submitted data is not valid."


class ConflictError(DomainError):
    """409 — the action conflicts with the current data."""

    status_code = 409
    default_message = "The action conflicts with the current state of the data."


class InsufficientStockError(ConflictError):
    default_message = "There is not enough non-expired stock."


class ExpiredBatchError(ConflictError):
    default_message = "The batch has expired."


class InvalidStateError(ConflictError):
    default_message = "The record is not in a state that allows this action."


class ProviderError(DomainError):
    """Not shown directly to the user — a notification provider failure."""

    status_code = 502
    default_message = "The delivery provider could not be reached."