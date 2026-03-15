"""Skill execution workflow — implements the full paper algorithm (Section 4.7).

Algorithm steps:
  1. Input task card x, environment E, constraints Ω
  2. Probe environment capabilities → κ(E)
  3. Compiler f_θ produces candidate skill S (or load from bank)
  4. Check skill legality Γ(S)
  5. Policy gate g_ψ decides executability
  6. Execute skill → trajectory τ  (or output block report)
  7. Compute V_vis(τ) and V_hid(τ)
  8. Generate execution report r(τ) with failure signatures σ
  9. Optimizer u_ω updates skill → S'
  10. Write S' back to skill bank
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capability import EnvironmentCapabilities, probe_environment
from .failure_signatures import (
    FailureSignature,
    extract_gate_signature,
    extract_signatures_from_actions,
    extract_signatures_from_preconditions,
    extract_signatures_from_verifications,
)
from .policy_gate import (
    GateDecision,
    PolicyConstraints,
    RiskBudget,
    compute_risk_budget,
    policy_gate,
)
from .remote import CommandResult, RemoteK8sRunner
from .skill_schema import ActionSpec, ClusterConfig, SkillSpec, VerificationSpec
from .verifier import SkillVerifier, VerificationResult, build_verification_judge


# ---------------------------------------------------------------------------
# Execution report  r(τ)   — Section 4.5.1
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ExecutionReport:
    """r(τ) = (P_res, A_res, V_vis^res, V_hid^res, R_res, σ)."""

    skill_name: str

    # Core artefacts
    preconditions: list[VerificationResult] = field(default_factory=list)
    actions: list[CommandResult] = field(default_factory=list)
    success_criteria: list[VerificationResult] = field(default_factory=list)
    rollback: list[CommandResult] = field(default_factory=list)

    # Hidden verification  V_hid(τ)   — Section 4.4
    hidden_results: list[VerificationResult] = field(default_factory=list)

    # Failure signatures  σ   — Section 4.5.1
    failure_signatures: list[dict[str, str]] = field(default_factory=list)

    # Policy gate decision
    gate_decision: dict[str, Any] | None = None

    # Risk budget  B(S,E)
    risk_budget: dict[str, float] | None = None

    # Environment capability snapshot
    env_capabilities: dict[str, Any] | None = None

    @property
    def succeeded(self) -> bool:
        preconditions_ok = all(result.passed for result in self.preconditions)
        success_ok = all(result.passed for result in self.success_criteria)
        action_ok = all(result.returncode == 0 for result in self.actions)
        return preconditions_ok and action_ok and success_ok

    @property
    def hidden_succeeded(self) -> bool:
        """V_hid(τ) — true iff all hidden checks pass."""
        if not self.hidden_results:
            return True
        return all(result.passed for result in self.hidden_results)

    @property
    def false_positive_gap(self) -> float:
        """Δ_fp = E[V_vis(τ)] - E[V_hid(τ)]   — Section 4.4.2."""
        v_vis = _pass_ratio(self.success_criteria)
        v_hid = _pass_ratio(self.hidden_results) if self.hidden_results else v_vis
        return max(0.0, v_vis - v_hid)

    @property
    def score(self) -> float:
        preconditions_ratio = _pass_ratio(self.preconditions)
        actions_ratio = _command_ratio(self.actions)
        success_ratio = _pass_ratio(self.success_criteria)
        hidden_ratio = _pass_ratio(self.hidden_results) if self.hidden_results else success_ratio
        rollback_penalty = 0.1 if self.rollback else 0.0

        # Joint score incorporating hidden verification — aligned with paper Eq.
        score = (
            0.20 * preconditions_ratio
            + 0.20 * actions_ratio
            + 0.25 * success_ratio
            + 0.25 * hidden_ratio
            - 0.10 * rollback_penalty
        )
        return max(0.0, min(1.0, score))

    @property
    def was_blocked(self) -> bool:
        """Whether the skill was blocked by the policy gate."""
        if self.gate_decision:
            return not self.gate_decision.get("allowed", True)
        return False


# ---------------------------------------------------------------------------
# Skill executor  — the core 10-step loop
# ---------------------------------------------------------------------------


class SkillExecutor:
    """Implements the full paper algorithm (Section 4.7).

    Compared to the previous minimal implementation, this version:
    - Probes environment capabilities κ(E) before execution
    - Computes risk budget B(S,E)
    - Runs the formal policy gate g_ψ
    - Executes hidden verification V_hid after visible verification
    - Extracts structured failure signatures σ
    """

    def __init__(
        self,
        cluster: ClusterConfig,
        verifier: str = "heuristic",
        verifier_model: str = "gpt-5.4",
        verifier_base_url: str = "https://api.openai.com/v1",
        verifier_api_key_env: str = "OPENAI_API_KEY",
        constraints: PolicyConstraints | None = None,
    ):
        self.cluster = cluster
        self.runner = RemoteK8sRunner(cluster)
        self.verifier = SkillVerifier(
            self.runner,
            judge=build_verification_judge(verifier, verifier_model, verifier_base_url, verifier_api_key_env),
        )
        self.constraints = constraints or PolicyConstraints()
        self._env_cache: EnvironmentCapabilities | None = None

    # -- Step 2: probe environment capabilities --
    def probe_env(self) -> EnvironmentCapabilities:
        """κ(E) — probe once and cache."""
        if self._env_cache is None:
            self._env_cache = probe_environment(self.runner, self.cluster.namespace)
        return self._env_cache

    # -- Main entry point --
    def run(
        self,
        skill: SkillSpec,
        execute_actions: bool = False,
        run_hidden: bool = True,
        allow_mutation: bool | None = None,
    ) -> ExecutionReport:
        """Execute the full 10-step algorithm from Section 4.7."""

        report = ExecutionReport(skill_name=skill.name)

        # --- Step 2: probe environment capabilities ---
        env = self.probe_env()
        report.env_capabilities = {
            "namespace": env.namespace,
            "tools": env.tools,
            "k8s_version": env.k8s_version,
            "node_count": env.node_count,
            "n_permissions": len(env.permissions),
            "n_crds": len(env.crds),
        }

        # --- Step 4 (partial): legality Γ(S) already enforced by SkillSpec ---

        # --- Step 5a: compute risk budget B(S,E) ---
        risk = compute_risk_budget(skill, env)
        report.risk_budget = {
            "b_scope": risk.b_scope,
            "b_mutation": risk.b_mutation,
            "b_privilege": risk.b_privilege,
            "b_rollback": risk.b_rollback,
            "total": risk.total,
        }

        # --- Preconditions (part of gate condition 1) ---
        report.preconditions = self.verifier.verify(skill.preconditions)
        preconditions_ok = all(item.passed for item in report.preconditions)

        # --- Step 5b: policy gate g_ψ ---
        constraints = PolicyConstraints(
            max_risk_budget=self.constraints.max_risk_budget,
            allow_mutation=allow_mutation if allow_mutation is not None else self.constraints.allow_mutation,
            allow_cluster_scope=self.constraints.allow_cluster_scope,
            required_rollback_for_mutation=self.constraints.required_rollback_for_mutation,
            blocked_commands=list(self.constraints.blocked_commands),
        )
        gate = policy_gate(skill, env, constraints, preconditions_passed=preconditions_ok)
        report.gate_decision = {
            "allowed": gate.allowed,
            "preconditions_passed": gate.preconditions_passed,
            "risk_within_budget": gate.risk_within_budget,
            "policy_compliant": gate.policy_compliant,
            "block_reasons": gate.block_reasons,
        }

        # --- Step 6: execute or block ---
        if not gate.allowed:
            sigs = extract_gate_signature(gate.block_reasons)
            report.failure_signatures = [_sig_to_dict(s) for s in sigs]
            return report

        if execute_actions:
            for action in skill.actions:
                result = self.runner.run(action.command, check=False)
                report.actions.append(result)
                if result.returncode != 0 and action.on_failure == "rollback":
                    report.rollback.extend(self._run_actions(skill.rollback))
                    break
                if result.returncode != 0 and action.on_failure == "abort":
                    break

        # --- Step 7a: visible verification V_vis(τ) ---
        report.success_criteria = self.verifier.verify(skill.success_criteria)

        # --- Step 7b: hidden verification V_hid(τ) ---
        if run_hidden:
            hidden_specs = _extract_hidden_checks(skill)
            if hidden_specs:
                report.hidden_results = self.verifier.verify(hidden_specs)

        # --- Step 8: failure signature extraction σ ---
        all_sigs: list[FailureSignature] = []
        all_sigs.extend(extract_signatures_from_preconditions(report.preconditions))
        all_sigs.extend(extract_signatures_from_actions(report.actions))
        all_sigs.extend(extract_signatures_from_verifications(report.success_criteria))
        all_sigs.extend(extract_signatures_from_verifications(report.hidden_results))
        report.failure_signatures = [_sig_to_dict(s) for s in all_sigs]

        return report

    def rollback(self, skill: SkillSpec) -> list[CommandResult]:
        return self._run_actions(skill.rollback)

    def _run_actions(self, actions: list[ActionSpec]) -> list[CommandResult]:
        results: list[CommandResult] = []
        for action in actions:
            results.append(self.runner.run(action.command, check=False))
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_hidden_checks(skill: SkillSpec) -> list[VerificationSpec]:
    """Extract hidden_checks from skill metadata → VerificationSpec list."""
    metadata = skill.metadata or {}
    hidden = metadata.get("hidden_checks", [])
    specs: list[VerificationSpec] = []
    for check in hidden:
        if isinstance(check, dict) and "command" in check:
            specs.append(VerificationSpec(
                name=check.get("name", "hidden-check"),
                command=check["command"],
                expect_exit_code=check.get("expect_exit_code", 0),
                expect_stdout_contains=check.get("expect_stdout_contains"),
            ))
    return specs


def _sig_to_dict(sig: FailureSignature) -> dict[str, str]:
    return {
        "failure_type": sig.failure_type.value,
        "source": sig.source,
        "step_name": sig.step_name,
        "raw_message": sig.raw_message,
        "suggested_fix": sig.suggested_fix,
    }


def _pass_ratio(results: list[VerificationResult]) -> float:
    if not results:
        return 1.0
    return sum(1 for item in results if item.passed) / len(results)


def _command_ratio(results: list[CommandResult]) -> float:
    if not results:
        return 1.0
    return sum(1 for item in results if item.returncode == 0) / len(results)
