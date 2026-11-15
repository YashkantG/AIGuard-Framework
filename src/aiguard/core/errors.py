"""Exception types raised by the service layer."""


class AIGuardError(Exception):
    """Base class for all AIGuard errors."""


class NotFoundError(AIGuardError):
    """A referenced record does not exist."""


class InvalidInputError(AIGuardError):
    """The request is well-formed but cannot be processed."""


class ConflictError(AIGuardError):
    """The request conflicts with existing state."""
