"""Errors shared by the gateway and the modules it delegates to."""


class Blocked(Exception):
    """The call was refused before it left the process."""
