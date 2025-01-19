import atexit
import enum
import os
import socket
import subprocess
import tempfile
import time

import pulumi as p
import pulumi_kubernetes as k8s


class ResourceType(enum.StrEnum):
    DEPLOYMENT = 'deployment'
    POD = 'pod'
    SERVICE = 'service'
    STATEFULSET = 'statefulset'


def ensure_port_forward(
    local_port: p.Input[int],
    namespace: p.Input[str],
    resource_type: ResourceType,
    resource_name: p.Input[str],
    target_port: p.Input[int | str],
    k8s_provider: k8s.Provider,
    skip_on_dry_run: bool = True,
    silent: bool = True,
) -> p.Output[int]:
    """
    Ensure that a port forward is established to the specified resource.

    Args:
        local_port: The local port to forward to the resource.
        namespace: The namespace of the resource.
        resource_type: The type of the resource to forward to.
        resource_name: The name of the resource to forward
        target_port: The target port (or port name) of the resource.
        k8s_provider: The Kubernetes provider to use.
        skip_on_dry_run: Whether to skip the port forward when running in dry-run mode.
        silent: Whether to suppress stdout.

    Returns:
        The local port given in local_port.
    """

    def callback(args) -> int:
        local_port = args['local_port']
        namespace = args['namespace']
        resource_type = args['resource_type']
        resource_name = args['resource_name']
        target_port = args['target_port']
        kubeconfig = args['kubeconfig']
        skip_on_dry_run = args['skip_on_dry_run']
        silent = args['silent']

        if skip_on_dry_run and p.runtime.is_dry_run():
            return local_port

        # Create a temporary kubeconfig file to use for the port forward.
        # Note that we delete the tempfile after the program exits to give
        # kubectl enough time to read the file.
        tmp_kubeconfig_file = tempfile.NamedTemporaryFile(delete=False)
        atexit.register(os.unlink, tmp_kubeconfig_file.name)

        # Write the kubeconfig file to the temporary file.
        tmp_kubeconfig_file.write(kubeconfig.encode())
        tmp_kubeconfig_file.flush()

        # Perform the port forward.
        extra_args = {}
        if silent:
            extra_args['stdout'] = subprocess.DEVNULL
        process = subprocess.Popen(
            [
                'kubectl',
                '--namespace',
                namespace,
                'port-forward',
                f'{resource_type}/{resource_name}',
                f'{local_port}:{target_port}',
            ],
            env={**os.environ, 'KUBECONFIG': tmp_kubeconfig_file.name},
            **extra_args,
        )

        # Wait for the port forward to be established.
        start = time.monotonic()
        while True:
            process.poll()
            if process.returncode is not None:
                raise Exception('Port forward process exited unexpectedly')
            try:
                s = socket.socket()
                s.connect(('localhost', local_port))
                s.close()
                break
            except ConnectionRefusedError:
                if time.monotonic() - start > 30:
                    raise Exception('Timed out waiting for port forward to be established')
                time.sleep(0.1)

        return local_port

    return p.Output.all(
        local_port=local_port,
        namespace=namespace,
        resource_type=resource_type,
        resource_name=resource_name,
        target_port=target_port,
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        skip_on_dry_run=skip_on_dry_run,
        silent=silent,
    ).apply(callback)
