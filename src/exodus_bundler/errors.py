class FatalError(Exception):
    """Base class for exceptions that should terminate program execution."""
    pass


class InvalidElfBinaryError(FatalError):
    """Signifies that a file was expected to be an ELF binary, but wasn't."""
    pass


class MissingFileError(FatalError):
    """Signifies that a file was not found."""
    pass
