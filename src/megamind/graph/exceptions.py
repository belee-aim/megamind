class WarehouseMatchError(Exception):
    """Custom exception raised when a warehouse name cannot be confidently matched."""

    def __init__(self, message, original_name=None, suggestions=None):
        super().__init__(message)
        self.original_name = original_name
        self.suggestions = suggestions if suggestions is not None else []

    def __str__(self):
        return f"{super().__str__()} (Original: '{self.original_name}', Suggestions: {len(self.suggestions)})"
