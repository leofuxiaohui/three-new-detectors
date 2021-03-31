class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class BlueprintAPIException(Error):
    def __init__(self, message: str):
        self.message = message


class InvalidBlueprintDataException(Error):
    def __init__(self, message: str):
        self.message = message
