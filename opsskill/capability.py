"""Environment capability probing — κ(E) in the paper.

Implements Section 4.2.2: probing permissions, objects, observation tools,
and cluster capabilities to inform the skill compiler and policy gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .remote import CommandResult, RemoteK8sRunner


@dataclass(slots=True)
class EnvironmentCapabilities:
    """κ(E) — the capability profile of a target environment.

    Fields correspond to the paper's four capability dimensions:
      permissions  — RBAC verbs available in the target namespace
      objects      — API resource types accessible
      tools        — CLI tools available (kubectl, helm, etc.)
      crds         — custom resource definitions installed
    """

    namespace: str = ""
    permissions: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    crds: list[str] = field(default_factory=list)
    k8s_version: str = "unknown"
    node_count: int = 0

    # Convenience predicates used by the policy gate

    def has_permission(self, verb: str, resource: str = "*") -> bool:
        """Check if a specific RBAC verb is available."""
        target = f"{verb}/*" if resource == "*" else f"{verb}/{resource}"
        for perm in self.permissions:
            if perm == target or perm == f"{verb}/*" or perm == "*/*":
                return True
        return False

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def has_crd(self, crd_name: str) -> bool:
        return any(crd_name in c for c in self.crds)


def probe_environment(runner: RemoteK8sRunner, namespace: str) -> EnvironmentCapabilities:
    """Probe the remote cluster to build κ(E).

    Runs a single SSH command that gathers all probes at once for efficiency.
    """
    cap = EnvironmentCapabilities(namespace=namespace)

    # Single compound command that gathers everything
    compound = (
        f"echo '===RBAC==='; kubectl auth can-i --list -n {namespace} 2>/dev/null | tail -n +2 | head -30; "
        f"echo '===API==='; kubectl api-resources --verbs=list --namespaced -o name 2>/dev/null | head -40; "
        f"echo '===TOOLS==='; for t in kubectl helm jq curl crictl; do command -v $t >/dev/null 2>&1 && echo $t; done; "
        f"echo '===CRD==='; kubectl get crd -o name 2>/dev/null | head -20; "
        f"echo '===VERSION==='; kubectl version -o json 2>/dev/null | grep gitVersion | head -1 || echo unknown; "
        f"echo '===NODES==='; kubectl get nodes --no-headers 2>/dev/null | wc -l"
    )
    result = runner.run(compound, check=False)
    if result.returncode != 0 and not result.stdout.strip():
        return cap

    # Parse sections
    sections: dict[str, list[str]] = {}
    current_key = ""
    for line in result.stdout.split("\n"):
        line = line.strip()
        if line.startswith("===") and line.endswith("==="):
            current_key = line.strip("=")
            sections[current_key] = []
        elif current_key and line:
            sections.setdefault(current_key, []).append(line)

    # 1. RBAC
    for line in sections.get("RBAC", []):
        parts = line.split()
        if len(parts) >= 2:
            resource = parts[0]
            verbs = parts[1].strip("[]").split() if len(parts) > 1 else []
            for verb in verbs:
                cap.permissions.append(f"{verb}/{resource}")

    # 2. API resources
    cap.objects = [l for l in sections.get("API", []) if l]

    # 3. Tools
    cap.tools = [l for l in sections.get("TOOLS", []) if l]

    # 4. CRDs
    cap.crds = [l.replace("customresourcedefinition.apiextensions.k8s.io/", "")
                for l in sections.get("CRD", []) if l]

    # 5. Version
    ver_lines = sections.get("VERSION", [])
    if ver_lines:
        cap.k8s_version = ver_lines[0].strip().strip('"').strip(",")

    # 6. Nodes
    node_lines = sections.get("NODES", [])
    if node_lines and node_lines[0].strip().isdigit():
        cap.node_count = int(node_lines[0].strip())

    return cap
