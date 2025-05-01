"""
This module contains utility functions.
"""

from pathlib import Path


def get_assets_path() -> Path:
    """
    Returns the path to the assets folder.
    """
    return Path(__file__).parent.parent / "assets"


def get_image(component: str):
    """
    Returns the image name for a given component.

    Each component is expected to have a Dockerfile in the assets folder so
    version updates can be automated via dependabot.
    """

    dockerfile = get_assets_path() / "docker" / component / "Dockerfile"
    with open(dockerfile, "r", encoding="UTF-8") as f:
        for line in f:
            if line.startswith("FROM"):
                return line.split()[1]
    raise RuntimeError(f"Could not find FROM statement in {dockerfile}.")
