"""
This module contains utility functions.
"""

import pathlib


def get_assets_path() -> pathlib.Path:
    """
    Returns the path to the assets folder.
    """
    return pathlib.Path(__file__).parent.parent / 'assets'
