import requests


def get_snap_version(package: str, channel: str, architecture: str) -> str:
    response = requests.get(
        f' https://api.snapcraft.io/v2/snaps/info/{package}', headers={'Snap-Device-Series': '16'}
    )
    data = response.json()

    versions = [
        version
        for version in data.get('channel-map')
        if version['channel']['name'] == channel
        if version['channel']['architecture'] == architecture
    ]
    assert len(versions) == 1, f'Expected 1 version, got {len(versions)}'

    return versions[0]['version']
