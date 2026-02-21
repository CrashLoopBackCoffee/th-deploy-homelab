import pathlib


def get_assets_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent / 'assets'
