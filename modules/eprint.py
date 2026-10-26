"""
Module for print to stderr functions.
3.0
"""

import pprint
import sys

debug_mode = False


def set_debug(value: bool):
    """
    Set debug mode.
    """
    global debug_mode
    debug_mode = value


def eprint(*args, **kwargs):
    """
    Print to stderr.
    """

    print(*args, file=sys.stderr, **kwargs)


def epprint(*args, **kwargs):
    """
    Prettyprint to stderr.
    """

    pretty_string = pprint.pformat(*args, **kwargs)
    eprint(pretty_string)


def debug_eprint(*args, **kwargs):
    """
    Debug print to stderr.
    """

    if debug_mode:
        eprint(*args, **kwargs)


def debug_epprint(*args, **kwargs):
    """
    Debug prettyprint to stderr.
    """

    if debug_mode:
        epprint(*args, **kwargs)
