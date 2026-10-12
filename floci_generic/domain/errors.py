"""Errors that cross the hexagon's boundary."""


class Blocked(Exception):
    """The call was refused before it left the process."""
