class IntunoError(Exception):
    """Base exception for all Intuno SDK errors."""

    pass


class APIKeyMissingError(IntunoError):
    """Raised when the API key is not provided."""

    def __init__(self, message="API key is required for authentication."):
        self.message = message
        super().__init__(self.message)


class AuthenticationError(IntunoError):
    """Raised when authentication fails."""

    pass


class InvocationError(IntunoError):
    """Raised when an agent invocation fails."""

    pass
