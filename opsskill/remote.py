from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass

from .skill_schema import ClusterConfig


@dataclass(slots=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


class RemoteK8sRunner:
    def __init__(self, cluster: ClusterConfig):
        self.cluster = cluster

    def run(self, command: str, check: bool = False, timeout: int = 60) -> CommandResult:
        remote_command = self._wrap_command(command)
        try:
            process = subprocess.run(
                remote_command,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                command=" ".join(remote_command),
                returncode=-1,
                stdout="",
                stderr=f"TIMEOUT after {timeout}s",
            )
        result = CommandResult(
            command=" ".join(remote_command),
            returncode=process.returncode,
            stdout=process.stdout.strip(),
            stderr=process.stderr.strip(),
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"Remote command failed with code {result.returncode}: {result.command}\n{result.stderr}"
            )
        return result

    def _wrap_command(self, command: str) -> list[str]:
        ssh_cmd = [
            "ssh",
            "-J", self.cluster.jump_host,
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=4",
            "-o", "ConnectTimeout=30",
        ]
        ssh_cmd.extend(self.cluster.ssh_options)
        ssh_cmd.append(self.cluster.target_host)
        kube_prefix = []
        if self.cluster.kube_context:
            kube_prefix.extend(["export", f"KUBECONFIG={shlex.quote(self.cluster.kube_context)}", "&&"])
        final_command = " ".join(kube_prefix + [f"export OPS_NAMESPACE={shlex.quote(self.cluster.namespace)}", "&&", command])
        ssh_cmd.append(final_command)
        return ssh_cmd
