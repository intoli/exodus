class FatalError(Exception):
    """Base class for exceptions that should terminate program execution."""
    pass


class InvalidElfBinaryError(FatalError):
    """Signifies that a file was expected to be an ELF binary, but wasn't."""
    pass


class LibraryConflictError(FatalError):
    """Signifies that two libraries with the same filename,
    but different file contents were encounterer."""
    pass


class MissingFileError(FatalError):
    """Signifies that a file was not found."""
    pass
