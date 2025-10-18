import pathlib
import textwrap

import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.unbound.host_override

from svn.config import ComponentConfig

HTTP_PORT = 80  # Service port
CONTAINER_PORT = 8080


def create_svn(component_config: ComponentConfig, k8s_provider: k8s.Provider) -> None:
    """
    Deploy Subversion (httpd variant) on Kubernetes.
    """
    assert component_config.svn

    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    namespace = k8s.core.v1.Namespace(
        'svn',
        metadata={'name': 'svn'},
        opts=k8s_opts,
    )

    # Persistent storage for repositories and config
    pvc = k8s.core.v1.PersistentVolumeClaim(
        'svn-data',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'svn-data',
        },
        spec={
            'access_modes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': '10Gi'}},
        },
        opts=k8s_opts.merge(p.ResourceOptions(delete_before_replace=True)),
    )

    app_labels = {'app': 'svn'}

    # Read httpd.conf override from assets (unchanged, large content)
    httpd_main_conf_path = pathlib.Path(__file__).resolve().parents[1] / 'assets' / 'httpd.conf'
    httpd_main_conf = httpd_main_conf_path.read_text()

    httpd_main_cm = k8s.core.v1.ConfigMap(
        'httpd-main-conf',
        metadata={'namespace': namespace.metadata.name},
        data={'httpd.conf': httpd_main_conf},
        opts=k8s_opts,
    )

    # Apache Subversion httpd include config using SVNParentPath for multiple repos
    httpd_config = textwrap.dedent(
        """
        ## SUBVERSION

        <Location /repos>
            DAV svn
            SVNParentPath /var/svn/repos
            SVNListParentPath on

            AuthType Basic
            AuthName "WebDAV/Subversion Authorization"
            AuthUserFile /var/svn/repos/conf/.htpasswd
            Require valid-user
        </Location>
        """
    ).strip()

    config_map = k8s.core.v1.ConfigMap(
        'svn-config',
        metadata={'namespace': namespace.metadata.name},
        data={'httpd-svn.conf': httpd_config},
        opts=k8s_opts,
    )

    # Build htpasswd content from configured users (expects pre-hashed passwords)
    users = component_config.svn.auth.users if component_config.svn.auth else []
    usernames = [u.username for u in users]
    hashes = p.Output.all(*[u.password_hash.value for u in users])
    htpasswd_content = hashes.apply(
        lambda h: '\n'.join(f'{usernames[i]}:{h[i]}' for i in range(len(h))) + '\n'
    )

    secret = k8s.core.v1.Secret(
        'svn-htpasswd',
        metadata={'namespace': namespace.metadata.name},
        type='Opaque',
        string_data={'htpasswd': p.Output.secret(htpasswd_content)},
        opts=k8s_opts,
    )

    deployment = k8s.apps.v1.Deployment(
        'svn',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'svn',
        },
        spec={
            'replicas': 1,
            'strategy': {
                'type': 'Recreate',
            },
            'selector': {'match_labels': app_labels},
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'security_context': {
                        'fs_group': 33,
                        'fs_group_change_policy': 'OnRootMismatch',
                    },
                    'init_containers': [
                        {
                            'name': 'init-svn-config',
                            # Use the same image so svnadmin is available
                            'image': f'obslib/subversion:{component_config.svn.version}',
                            'security_context': {
                                'run_as_non_root': True,
                                'run_as_user': 33,
                                'run_as_group': 33,
                                'allow_privilege_escalation': False,
                            },
                            'command': ['/bin/sh', '-c'],
                            'args': [
                                '\n'.join(
                                    [
                                        'set -eu',
                                        # Ensure directory structure for config exists (multi-repo parent)
                                        'mkdir -p /var/svn/repos/conf',
                                        # Ensure parent dir has SGID so new repos inherit group www-data
                                        'chgrp 33 /var/svn/repos || true',
                                        'chmod 2775 /var/svn/repos || true',
                                    ]
                                ),
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'svn-data',
                                    'mount_path': '/var/svn',
                                },
                            ],
                        }
                    ],
                    'containers': [
                        {
                            'name': 'svn',
                            # Expect full tag including httpd variant, e.g. "httpd-1.14.2"
                            'image': f'obslib/subversion:{component_config.svn.version}',
                            'ports': [{'name': 'http', 'container_port': CONTAINER_PORT}],
                            'security_context': {
                                'run_as_non_root': True,
                                'run_as_user': 33,
                                'run_as_group': 33,
                                'allow_privilege_escalation': False,
                            },
                            'volume_mounts': [
                                {
                                    'name': 'svn-data',
                                    # Image expects repos under /var/svn
                                    'mount_path': '/var/svn',
                                },
                                {
                                    'name': 'httpd-main-conf',
                                    'mount_path': '/usr/local/httpd/conf/httpd.conf',
                                    'sub_path': 'httpd.conf',
                                    'read_only': True,
                                },
                                {
                                    'name': 'httpd-logs',
                                    'mount_path': '/usr/local/httpd/logs',
                                },
                                {
                                    'name': 'svn-config',
                                    'mount_path': '/var/svn/repos/conf/httpd-svn.conf',
                                    'sub_path': 'httpd-svn.conf',
                                    'read_only': True,
                                },
                                {
                                    'name': 'svn-htpasswd',
                                    'mount_path': '/var/svn/repos/conf/.htpasswd',
                                    'sub_path': 'htpasswd',
                                    'read_only': True,
                                },
                            ],
                            'resources': {
                                'requests': {
                                    'memory': component_config.svn.resources.memory,
                                    'cpu': component_config.svn.resources.cpu,
                                },
                            },
                            'readiness_probe': {
                                'http_get': {
                                    'path': '/',
                                    'port': CONTAINER_PORT,
                                },
                                'period_seconds': 15,
                            },
                        },
                    ],
                    'volumes': [
                        {
                            'name': 'svn-data',
                            'persistent_volume_claim': {'claim_name': pvc.metadata.name},
                        },
                        {
                            'name': 'httpd-main-conf',
                            'config_map': {
                                'name': httpd_main_cm.metadata.name,
                            },
                        },
                        {
                            'name': 'httpd-logs',
                            'empty_dir': {},
                        },
                        {
                            'name': 'svn-config',
                            'config_map': {
                                'name': config_map.metadata.name,
                            },
                        },
                        {
                            'name': 'svn-htpasswd',
                            'secret': {
                                'secret_name': secret.metadata.name,
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    service = k8s.core.v1.Service(
        'svn',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'svn',
        },
        spec={
            'ports': [{'name': 'http', 'port': HTTP_PORT, 'target_port': CONTAINER_PORT}],
            'selector': deployment.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )

    # Local DNS mapping to Traefik load balancer IP
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'svn',
        host='svn',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # IngressRoute for TLS via Traefik
    fqdn = f'svn.{component_config.cloudflare.zone}'
    k8s.apiextensions.CustomResource(
        'ingress',
        api_version='traefik.io/v1alpha1',
        kind='IngressRoute',
        metadata={
            'name': 'ingress',
            'namespace': namespace.metadata.name,
        },
        spec={
            'entryPoints': ['websecure'],
            'routes': [
                {
                    'kind': 'Rule',
                    'match': p.Output.concat('Host(`', fqdn, '`)'),
                    'services': [
                        {
                            'name': service.metadata.name,
                            'namespace': service.metadata.namespace,
                            'port': HTTP_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    p.export('svn_url', p.Output.format('https://{}.{}', record.host, record.domain))
