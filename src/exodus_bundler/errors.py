# -*- coding: utf-8 -*-
class FatalError(Exception):
    """Base class for exceptions that should terminate program execution."""
    pass


class DependencyDetectionError(FatalError):
    """Signifies that the dependency detection process failed."""
    pass


class InvalidElfBinaryError(FatalError):
    """Signifies that a file was expected to be an ELF binary, but wasn't."""
    pass


class MissingFileError(FatalError):
    """Signifies that a file was not found."""
    pass


class UnexpectedDirectoryError(FatalError):
    """Signifies that a path was unexpectedly a directory."""
    pass


class UnsupportedArchitectureError(FatalError):
    """Signifies that a binary has an unexpected architecture."""
    pass
