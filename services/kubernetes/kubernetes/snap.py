import requests


def get_snap_version(package: str, channel: str, architecture: str) -> str:
    """Return the current version string of a snap for a given channel and architecture.

    This queries the Snap Store API and filters the channel-map entries to find the
    exact match for the provided channel (e.g. "1.31/stable") and architecture (e.g. "amd64").
    """
    response = requests.get(
        f'https://api.snapcraft.io/v2/snaps/info/{package}',
        headers={'Snap-Device-Series': '16'},
        timeout=10,
    )
    data = response.json()

    versions = [
        version
        for version in data.get('channel-map', [])
        if version.get('channel', {}).get('name') == channel
        and version.get('channel', {}).get('architecture') == architecture
    ]
    assert len(versions) == 1, f'Expected 1 version, got {len(versions)}'

    return versions[0]['version']
