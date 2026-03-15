"""Skill optimizer — u_ω in the paper (Section 4.5).

Implements:
  - Failure-signature-driven structural edits  Δ_σ(S)
  - Projection back to legal skill space       Π_{S_k}
  - Both heuristic and LLM-assisted optimisation
  - Skill write-back to the skill bank (Step 10)
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from .failure_signatures import FailureSignature, FailureType
from .llm import LLMConfig, OpenAICompatibleLLM
from .skill_schema import SkillSpec, SkillValidationError, VerificationSpec
from .workflow import ExecutionReport


# ---------------------------------------------------------------------------
# Text-level suggestions (kept for backward compatibility with CLI review)
# ---------------------------------------------------------------------------


def suggest_improvements(report: ExecutionReport) -> list[str]:
    suggestions: list[str] = []

    failed_preconditions = [item for item in report.preconditions if not item.passed]
    failed_actions = [item for item in report.actions if item.returncode != 0]
    failed_success = [item for item in report.success_criteria if not item.passed]

    if failed_preconditions:
        suggestions.append("Tighten preconditions so the skill only targets workloads that definitely exist and are reachable.")
        suggestions.append("Add a capability probe step for namespace, RBAC, and required CRDs before any action step.")
    if failed_actions:
        suggestions.append("Split large actions into smaller reversible steps and attach rollback to the first mutating command.")
        suggestions.append("Capture stderr patterns from the failing action and promote them into future routing or guard rules.")
    if failed_success:
        suggestions.append("Strengthen success criteria with rollout, pod readiness, and service-level checks instead of a single command exit code.")
        suggestions.append("Add post-check telemetry such as Prometheus or events so the verifier can detect partial recovery.")
    if report.rollback:
        suggestions.append("Minimize rollback frequency by adding a dry-run or canary namespace stage before the mutating action.")
    if not suggestions:
        suggestions.append("Promote this skill to the registry baseline and replay it on more namespaces or clusters to test portability.")
        suggestions.append("Add latency and token-cost telemetry so optimization can trade off success, speed, and resource cost.")

    return suggestions


# ---------------------------------------------------------------------------
# Structured skill update  u_ω(S, r(τ))  — Section 4.5.2
# ---------------------------------------------------------------------------


def _apply_structural_edits(
    skill_dict: dict[str, Any],
    signatures: list[dict[str, str]],
) -> dict[str, Any]:
    """Apply Δ_σ(S) — signature-driven edits to a skill dictionary.

    Corresponds to the paper's mapping from failure types to structural
    edits (Section 4.5.2, bullet list):
      RESOURCE_NOT_FOUND  → add/strengthen precondition
      RBAC_DENIED         → narrow action scope, add RBAC precondition
      ROLLOUT_TIMEOUT     → add intermediate check, strengthen rollback
      READINESS_NOT_MET   → add hidden verification signal
    """
    preconditions = list(skill_dict.get("preconditions", []))
    rollback = list(skill_dict.get("rollback", []))
    metadata = dict(skill_dict.get("metadata", {}))
    ns = skill_dict.get("namespace", "opsskill-sandbox")

    existing_precond_names = {p.get("name", "") for p in preconditions}

    for sig in signatures:
        ftype = sig.get("failure_type", "")

        if ftype == FailureType.RESOURCE_NOT_FOUND.value:
            new_name = "verify-target-resource-exists"
            if new_name not in existing_precond_names:
                preconditions.append({
                    "name": new_name,
                    "command": f"kubectl -n {ns} get all --no-headers | head -5",
                })
                existing_precond_names.add(new_name)

        elif ftype == FailureType.RBAC_DENIED.value:
            new_name = "verify-rbac-permissions"
            if new_name not in existing_precond_names:
                preconditions.append({
                    "name": new_name,
                    "command": f"kubectl auth can-i list pods -n {ns}",
                })
                existing_precond_names.add(new_name)

        elif ftype == FailureType.ROLLOUT_TIMEOUT.value:
            # Strengthen rollback if missing
            if not rollback:
                actions = skill_dict.get("actions", [])
                for act in actions:
                    cmd = act.get("command", "")
                    if "rollout restart" in cmd and "deployment/" in cmd:
                        deploy_name = cmd.split("deployment/")[-1].split()[0]
                        rollback.append({
                            "name": f"undo-rollout-{deploy_name}",
                            "command": f"kubectl -n {ns} rollout undo deployment/{deploy_name}",
                        })

        elif ftype == FailureType.READINESS_NOT_MET.value:
            hidden_checks = list(metadata.get("hidden_checks", []))
            hc_name = "pod-readiness-signal"
            if not any(h.get("name") == hc_name for h in hidden_checks):
                hidden_checks.append({
                    "name": hc_name,
                    "signal": "pod-readiness",
                    "command": f"kubectl -n {ns} get pods -o jsonpath='{{range .items[*]}}{{.metadata.name}}={{.status.phase}}\\n{{end}}'",
                })
                metadata["hidden_checks"] = hidden_checks

        elif ftype == FailureType.CRD_MISSING.value:
            new_name = "verify-crd-available"
            if new_name not in existing_precond_names:
                preconditions.append({
                    "name": new_name,
                    "command": "kubectl get crd --no-headers | head -5",
                })
                existing_precond_names.add(new_name)

        elif ftype == FailureType.COMMAND_NOT_FOUND.value:
            new_name = "verify-tools-available"
            if new_name not in existing_precond_names:
                preconditions.append({
                    "name": new_name,
                    "command": "command -v kubectl && echo ok",
                    "expect_stdout_contains": "ok",
                })
                existing_precond_names.add(new_name)

    skill_dict["preconditions"] = preconditions
    skill_dict["rollback"] = rollback
    skill_dict["metadata"] = metadata
    return skill_dict


def _project_to_skill_space(skill_dict: dict[str, Any]) -> dict[str, Any]:
    """Π_{S_k} — project back to legal skill space.

    Ensures the edited skill still satisfies Γ(S) = 1.
    """
    # Ensure required fields
    skill_dict.setdefault("version", "0.1")
    skill_dict.setdefault("name", "unnamed-skill")
    skill_dict.setdefault("intent", "auto-generated")
    skill_dict.setdefault("namespace", "opsskill-sandbox")
    skill_dict.setdefault("actions", [])
    skill_dict.setdefault("success_criteria", [])

    if not skill_dict["actions"]:
        skill_dict["actions"] = [{"name": "placeholder", "command": "echo 'no-op'"}]
    if not skill_dict["success_criteria"]:
        skill_dict["success_criteria"] = [{"name": "placeholder", "command": "echo ok"}]

    # Validate by parsing
    try:
        SkillSpec.from_dict(skill_dict)
    except SkillValidationError:
        pass  # Best-effort: return dict as-is for manual review
    return skill_dict


class HeuristicOptimizer:
    """u_ω (heuristic) — applies Δ_σ directly and projects back."""

    name = "heuristic"

    def suggest(self, report: ExecutionReport) -> list[str]:
        return suggest_improvements(report)

    def update_skill(
        self,
        skill: SkillSpec,
        report: ExecutionReport,
    ) -> dict[str, Any]:
        """u_ω(S, r(τ)) = Π_{S_k}(S + Δ_σ(S))."""
        # Serialize skill to dict for editing
        skill_dict = _skill_to_dict(skill)
        # Apply structural edits based on failure signatures
        skill_dict = _apply_structural_edits(skill_dict, report.failure_signatures)
        # Project back to legal skill space
        skill_dict = _project_to_skill_space(skill_dict)
        return skill_dict


class LLMOptimizer:
    """u_ω (LLM-assisted) — uses LLM to refine edits, with heuristic fallback."""

    name = "llm"

    def __init__(self, config: LLMConfig, fallback: HeuristicOptimizer | None = None):
        self.client = OpenAICompatibleLLM(config)
        self.fallback = fallback or HeuristicOptimizer()

    def suggest(self, report: ExecutionReport) -> list[str]:
        system_prompt = (
            "You are an Ops skill optimization agent. Given an execution report, produce concise suggestions that improve hidden success, safety, and efficiency. "
            "Return strict JSON with key 'suggestions' as a list of short strings."
        )
        user_payload = {
            "skill_name": report.skill_name,
            "preconditions": [item.detail for item in report.preconditions],
            "actions": [{"command": item.command, "returncode": item.returncode, "stderr": item.stderr} for item in report.actions],
            "success": [item.detail for item in report.success_criteria],
            "rollback": [{"command": item.command, "returncode": item.returncode} for item in report.rollback],
            "failure_signatures": report.failure_signatures,
            "score": report.score,
            "succeeded": report.succeeded,
        }
        try:
            result = self.client.complete_json(system_prompt, user_payload)
            suggestions = result.get("suggestions", [])
            if isinstance(suggestions, list) and suggestions:
                return [str(item) for item in suggestions]
            raise RuntimeError("LLM optimizer returned no suggestions")
        except Exception:
            return self.fallback.suggest(report)

    def update_skill(
        self,
        skill: SkillSpec,
        report: ExecutionReport,
    ) -> dict[str, Any]:
        """u_ω(S, r(τ)) with LLM-assisted refinement."""
        # First apply heuristic structural edits
        skill_dict = self.fallback.update_skill(skill, report)
        # Then ask LLM to refine
        system_prompt = (
            "You are a safe Ops skill optimizer. Given a skill YAML and its execution report with failure signatures, "
            "return an improved skill as strict JSON. Preserve all required fields (version, name, intent, namespace, "
            "actions, success_criteria). Focus on: strengthening preconditions, adding rollback, improving verification. "
            "Return the complete updated skill object as JSON."
        )
        user_payload = {
            "current_skill": skill_dict,
            "failure_signatures": report.failure_signatures,
            "score": report.score,
            "hidden_score": _pass_ratio_list(report.hidden_results),
        }
        try:
            refined = self.client.complete_json(system_prompt, user_payload)
            refined = _project_to_skill_space(refined)
            return refined
        except Exception:
            return skill_dict


def build_optimizer(
    optimizer: str = "heuristic",
    model: str = "gpt-5.4",
    base_url: str = "https://api.openai.com/v1",
    api_key_env: str = "OPENAI_API_KEY",
) -> HeuristicOptimizer | LLMOptimizer:
    if optimizer == "llm":
        return LLMOptimizer(LLMConfig(model=model, base_url=base_url, api_key_env=api_key_env))
    return HeuristicOptimizer()


# ---------------------------------------------------------------------------
# Step 10: write updated skill back to skill bank
# ---------------------------------------------------------------------------


def write_back_skill(skill_dict: dict[str, Any], path: str | Path) -> SkillSpec:
    """Write updated skill S' back to the skill bank."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(skill_dict, fh, sort_keys=False, allow_unicode=True)
    return SkillSpec.from_dict(skill_dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill_to_dict(skill: SkillSpec) -> dict[str, Any]:
    """Serialize a SkillSpec back to a plain dict for editing."""
    return {
        "version": skill.version,
        "name": skill.name,
        "intent": skill.intent,
        "namespace": skill.namespace,
        "metadata": copy.deepcopy(skill.metadata),
        "preconditions": [
            {"name": p.name, "command": p.command, "expect_exit_code": p.expect_exit_code,
             **({"expect_stdout_contains": p.expect_stdout_contains} if p.expect_stdout_contains else {})}
            for p in skill.preconditions
        ],
        "actions": [
            {"name": a.name, "command": a.command, "on_failure": a.on_failure}
            for a in skill.actions
        ],
        "success_criteria": [
            {"name": v.name, "command": v.command, "expect_exit_code": v.expect_exit_code,
             **({"expect_stdout_contains": v.expect_stdout_contains} if v.expect_stdout_contains else {})}
            for v in skill.success_criteria
        ],
        "rollback": [
            {"name": r.name, "command": r.command}
            for r in skill.rollback
        ],
    }


def _pass_ratio_list(results: list) -> float:
    if not results:
        return 1.0
    return sum(1 for item in results if item.passed) / len(results)
