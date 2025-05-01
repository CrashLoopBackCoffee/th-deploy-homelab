import pulumi as p
import pulumi_proxmoxve as proxmoxve


def download_iso_local(
    name: str,
    *,
    url: p.Input[str],
    filename: p.Input[str],
    node_name: p.Input[str],
    provider: proxmoxve.Provider,
) -> proxmoxve.download.File:
    return proxmoxve.download.File(
        name,
        content_type='iso',
        datastore_id='local',
        node_name=node_name,
        overwrite=False,
        url=url,
        file_name=filename,
        opts=p.ResourceOptions(provider=provider, delete_before_replace=True),
    )
