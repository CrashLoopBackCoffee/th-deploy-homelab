import pathlib

import pulumi as p


def directory_content(path: pathlib.Path) -> list[str]:
    """
    Hashes the contents of a directory.
    """
    contents = []
    for file in path.rglob('*'):
        if file.is_file():
            contents.append(file.read_text())
    return contents


def stack_is_prod() -> bool:
    return p.get_stack() == 'prod'
