"""
Create a CouchDB server
"""

import pulumi
import pulumi_command
import pulumi_docker as docker
import pulumi_random
from pulumi import Output, ResourceOptions

from obsidian.utils import get_assets_path, get_image


def create_couchdb(network: docker.Network, opts: ResourceOptions):
    """
    Deploy CouchDB server
    """
    config = pulumi.Config()

    target_root_dir = config.get("root-dir")
    target_host = config.get("target-host")
    target_user = config.get("target-user")

    couchdb_user = config.get("couchdb-user")
    couchdb_password = pulumi_random.RandomPassword("couchdb-password", length=36)
    pulumi.export("couchdb-user", couchdb_user)
    pulumi.export("couchdb-password", couchdb_password.result)

    couchdb_config_dir_resource = pulumi_command.remote.Command(
        "create-couchdb-config",
        connection=pulumi_command.remote.ConnectionArgs(
            host=target_host, user=target_user
        ),
        create=f"mkdir -p {target_root_dir}/obsidian-config",
    )

    couchdb_data_dir_resource = pulumi_command.remote.Command(
        "create-couchdb-data",
        connection=pulumi_command.remote.ConnectionArgs(
            host=target_host, user=target_user
        ),
        create=f"mkdir -p {target_root_dir}/obsidian-data",
    )

    config_source_path = get_assets_path() / "couchdb"
    sync_command = (
        f"rsync --rsync-path /bin/rsync -av --delete --no-perms --no-owner --no-group "
        f"{config_source_path}/ "
        f"{target_user}@{target_host}:{target_root_dir}/obsidian-config/"
    )

    with open(config_source_path / "docker.ini", "r", encoding="UTF-8") as f:
        config_lines = [line.strip() for line in f.readlines()]
    couchdb_config = pulumi_command.local.Command(
        "couchdb-config",
        create=sync_command,
        triggers=[config_lines, couchdb_config_dir_resource.id],
    )

    image = docker.RemoteImage(
        "couchdb",
        name=get_image("couchdb"),
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        "obsidian-couchdb",
        image=image.image_id,
        name="obsidian-couchdb",
        envs=[
            f"COUCHDB_USER={couchdb_user}",
            Output.format("COUCHDB_PASSWORD={}", couchdb_password.result),
            Output.format("COUCHDB_CONFIG_VERSION={}", couchdb_config.id),
        ],
        volumes=[
            docker.ContainerVolumeArgs(
                host_path=f"{target_root_dir}/obsidian-config",
                container_path="/opt/couchdb/etc/local.d",
            ),
            docker.ContainerVolumeArgs(
                host_path=f"{target_root_dir}/obsidian-data",
                container_path="/opt/couchdb/data",
            ),
        ],
        networks_advanced=[
            docker.ContainerNetworksAdvancedArgs(
                name=network.name, aliases=["obsidian-couchdb"]
            ),
        ],
        restart="always",
        start=True,
        opts=opts.merge(
            ResourceOptions(
                depends_on=[
                    couchdb_data_dir_resource,
                    couchdb_config_dir_resource,
                    couchdb_config,
                ]
            )
        ),
    )
