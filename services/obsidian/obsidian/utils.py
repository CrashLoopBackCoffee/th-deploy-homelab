"""
This module contains utility functions.
"""

from pathlib import Path


def get_assets_path() -> Path:
    """
    Returns the path to the assets folder.
    """
    return Path(__file__).parent.parent / 'assets'
