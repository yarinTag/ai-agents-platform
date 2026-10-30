"""Public orchestration failures shared by delegation and coordination."""


class DelegationError(ValueError):
    """Raised when task delegation violates hierarchy, permissions, or rules."""
    pass


class ConcurrencyLimitExceededError(DelegationError):
    """Raised when an agent reaches or exceeds maximum allowed concurrent subtasks."""
    pass


