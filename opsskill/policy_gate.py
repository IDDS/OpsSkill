"""Risk budget computation and policy gating — B(S,E) and g_ψ in the paper.

Implements Section 4.3:
  - Risk function B(S,E) = w1·b_scope + w2·b_mutation + w3·b_privilege + w4·b_rollback
  - Policy gate  g_ψ(S, κ(E), Ω) = I[P=1] · I[B≤b_max] · I[policy=1]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capability import EnvironmentCapabilities
from .skill_schema import SkillSpec


# ---------------------------------------------------------------------------
# Risk budget  B(S, E)   — Section 4.3.1
# ---------------------------------------------------------------------------

# Default weights (can be overridden via constraints)
_W_SCOPE = 0.25
_W_MUTATION = 0.35
_W_PRIVILEGE = 0.20
_W_ROLLBACK = 0.20


@dataclass(slots=True)
class RiskBudget:
    """Decomposed risk assessment for a skill in a given environment."""

    b_scope: float = 0.0       # 0 = namespace-local, 1 = cluster-wide
    b_mutation: float = 0.0    # 0 = read-only, 1 = destructive mutation
    b_privilege: float = 0.0   # 0 = no special RBAC, 1 = requires cluster-admin
    b_rollback: float = 0.0    # 0 = rollback exists and tested, 1 = no rollback

    @property
    def total(self) -> float:
        """Weighted risk score B(S,E)."""
        return (
            _W_SCOPE * self.b_scope
            + _W_MUTATION * self.b_mutation
            + _W_PRIVILEGE * self.b_privilege
            + _W_ROLLBACK * self.b_rollback
        )


def compute_risk_budget(skill: SkillSpec, env: EnvironmentCapabilities) -> RiskBudget:
    """Compute B(S, E) for a skill given environment capabilities."""
    metadata = skill.metadata or {}
    risk_level = str(metadata.get("risk_level", "unknown")).lower()
    category = str(metadata.get("category", "unknown")).lower()
    target_kind = str(metadata.get("target_kind", "")).lower()

    # b_scope: namespace-local vs cluster-wide
    action_cmds = " ".join(a.command for a in skill.actions)
    is_cluster_scope = (
        "--all-namespaces" in action_cmds
        or "-A " in action_cmds
        or "clusterrole" in action_cmds.lower()
        or "node" in target_kind
    )
    b_scope = 1.0 if is_cluster_scope else 0.0

    # b_mutation: read-only vs mutating
    _mutating_verbs = {"delete", "patch", "apply", "create", "scale", "rollout restart", "edit", "replace", "drain", "cordon", "taint"}
    has_mutation = any(verb in action_cmds.lower() for verb in _mutating_verbs)
    mutation_map = {"action": 0.8, "mutation": 1.0, "observation": 0.0, "analysis": 0.1}
    b_mutation = mutation_map.get(category, 0.5 if has_mutation else 0.0)
    if risk_level == "high":
        b_mutation = max(b_mutation, 0.9)
    elif risk_level == "none":
        b_mutation = min(b_mutation, 0.1)

    # b_privilege: does skill require elevated RBAC?
    required_tools = metadata.get("required_tools", [])
    needs_helm = "helm" in required_tools
    needs_admin_verbs = any(v in action_cmds for v in ["cluster-admin", "clusterrolebinding", "psp"])
    b_privilege = 0.0
    if needs_admin_verbs:
        b_privilege = 1.0
    elif needs_helm:
        b_privilege = 0.5
    elif has_mutation:
        b_privilege = 0.3

    # b_rollback: does the skill provide rollback for mutating actions?
    has_rollback = bool(skill.rollback)
    if has_mutation and not has_rollback:
        b_rollback = 1.0
    elif has_mutation and has_rollback:
        b_rollback = 0.2
    else:
        b_rollback = 0.0

    return RiskBudget(
        b_scope=b_scope,
        b_mutation=b_mutation,
        b_privilege=b_privilege,
        b_rollback=b_rollback,
    )


# ---------------------------------------------------------------------------
# Policy constraints  Ω   — Section 4.3.2
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PolicyConstraints:
    """Ω — operational policy constraints for gating execution."""

    max_risk_budget: float = 0.6          # b_max in the paper
    allow_mutation: bool = False
    allow_cluster_scope: bool = False
    required_rollback_for_mutation: bool = True
    blocked_commands: list[str] = field(default_factory=lambda: [
        "kubectl delete namespace",
        "kubectl drain",
        "kubectl cordon",
    ])


# ---------------------------------------------------------------------------
# Gate report  — structured output when a skill is blocked
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GateDecision:
    """Result of the policy gate g_ψ."""

    allowed: bool
    preconditions_passed: bool
    risk_within_budget: bool
    policy_compliant: bool
    risk_budget: RiskBudget | None = None
    block_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy gate  g_ψ(S, κ(E), Ω)   — Section 4.3.2
# ---------------------------------------------------------------------------


def policy_gate(
    skill: SkillSpec,
    env: EnvironmentCapabilities,
    constraints: PolicyConstraints,
    preconditions_passed: bool = True,
) -> GateDecision:
    """Evaluate g_ψ(S, κ(E), Ω) = I[P=1] · I[B≤b_max] · I[policy=1].

    Returns a GateDecision with detailed block reasons if any condition fails.
    """
    risk = compute_risk_budget(skill, env)
    block_reasons: list[str] = []

    # Condition 1: preconditions must have passed  — I[P(S,E) = 1]
    cond_precond = preconditions_passed
    if not cond_precond:
        block_reasons.append("Precondition check failed — environment not ready for this skill")

    # Condition 2: risk within budget  — I[B(S,E) ≤ b_max]
    cond_risk = risk.total <= constraints.max_risk_budget
    if not cond_risk:
        block_reasons.append(
            f"Risk budget exceeded: B={risk.total:.3f} > b_max={constraints.max_risk_budget:.3f} "
            f"(scope={risk.b_scope:.2f}, mutation={risk.b_mutation:.2f}, "
            f"privilege={risk.b_privilege:.2f}, rollback={risk.b_rollback:.2f})"
        )

    # Condition 3: policy compliance  — I[policy(S, Ω) = 1]
    cond_policy = True
    metadata = skill.metadata or {}
    category = str(metadata.get("category", "")).lower()
    is_mutating = category == "action" or risk.b_mutation > 0.3

    if is_mutating and not constraints.allow_mutation:
        cond_policy = False
        block_reasons.append("Mutating skill blocked by policy: allow_mutation=False")

    if risk.b_scope > 0 and not constraints.allow_cluster_scope:
        cond_policy = False
        block_reasons.append("Cluster-scope skill blocked by policy: allow_cluster_scope=False")

    if is_mutating and not skill.rollback and constraints.required_rollback_for_mutation:
        cond_policy = False
        block_reasons.append("Mutating skill without rollback blocked by policy")

    # Check for blocked commands
    action_cmds = " ".join(a.command.lower() for a in skill.actions)
    for blocked in constraints.blocked_commands:
        if blocked.lower() in action_cmds:
            cond_policy = False
            block_reasons.append(f"Blocked command detected: '{blocked}'")

    # Check required tools are available
    required_tools = metadata.get("required_tools", [])
    for tool in required_tools:
        if not env.has_tool(tool):
            cond_policy = False
            block_reasons.append(f"Required tool '{tool}' not available in environment")

    allowed = cond_precond and cond_risk and cond_policy
    return GateDecision(
        allowed=allowed,
        preconditions_passed=cond_precond,
        risk_within_budget=cond_risk,
        policy_compliant=cond_policy,
        risk_budget=risk,
        block_reasons=block_reasons,
    )
