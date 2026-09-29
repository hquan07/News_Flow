class DependencyUnavailableError(RuntimeError):
    """Raised when an external service cannot satisfy an API request."""

    def __init__(self, dependency: str):
        self.dependency = dependency
        super().__init__(f"{dependency} is unavailable")
