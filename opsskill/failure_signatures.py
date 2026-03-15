"""Failure signature extraction — σ in the paper.

Implements Section 4.5.1: extracts structured failure signatures from
execution reports to drive the optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .remote import CommandResult
from .verifier import VerificationResult


class FailureType(str, Enum):
    """Structured failure types from the paper (Section 4.5.1)."""

    RBAC_DENIED = "RBAC_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    ROLLOUT_TIMEOUT = "ROLLOUT_TIMEOUT"
    READINESS_NOT_MET = "READINESS_NOT_MET"
    CRD_MISSING = "CRD_MISSING"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    COMMAND_NOT_FOUND = "COMMAND_NOT_FOUND"
    IMAGE_PULL_FAILED = "IMAGE_PULL_FAILED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class FailureSignature:
    """A single structured failure extracted from an execution step."""

    failure_type: FailureType
    source: str         # "precondition" | "action" | "verification" | "gate"
    step_name: str
    raw_message: str    # stderr or detail snippet
    suggested_fix: str  # mapping Δ_σ hint


# ---------------------------------------------------------------------------
# Pattern matching rules for stderr / detail → FailureType
# ---------------------------------------------------------------------------

_PATTERN_MAP: list[tuple[list[str], FailureType]] = [
    (["forbidden", "rbac", "cannot list", "cannot get", "cannot create", "cannot delete", "cannot patch", "unauthorized"],
     FailureType.RBAC_DENIED),
    (["not found", "notfound", "no resources found", "doesn't have a resource type", "the server doesn't have"],
     FailureType.RESOURCE_NOT_FOUND),
    (["timed out", "timeout", "deadline exceeded", "context deadline"],
     FailureType.ROLLOUT_TIMEOUT),
    (["readiness", "not ready", "0/1", "unavailable", "crashloopbackoff", "pending"],
     FailureType.READINESS_NOT_MET),
    (["no matches for kind", "crd", "customresourcedefinition", "no kind"],
     FailureType.CRD_MISSING),
    (["connection refused", "connect: connection refused", "dial tcp"],
     FailureType.CONNECTION_REFUSED),
    (["command not found", "not found in PATH", "executable file not found"],
     FailureType.COMMAND_NOT_FOUND),
    (["imagepullbackoff", "errimagepull", "image pull", "manifest unknown"],
     FailureType.IMAGE_PULL_FAILED),
]

# Maps FailureType → structured edit hints (Δ_σ from paper Section 4.5.2)
_FIX_MAP: dict[FailureType, str] = {
    FailureType.RBAC_DENIED: "Add RBAC precondition; narrow action scope to namespace-level verbs",
    FailureType.RESOURCE_NOT_FOUND: "Strengthen precondition to verify resource existence before action",
    FailureType.ROLLOUT_TIMEOUT: "Add intermediate readiness checks; increase timeout; strengthen rollback",
    FailureType.READINESS_NOT_MET: "Add hidden verification signals for pod readiness; refine action granularity",
    FailureType.CRD_MISSING: "Add CRD existence precondition; provide fallback for environments without CRD",
    FailureType.POLICY_BLOCKED: "Lower risk level or add rollback to pass policy gate",
    FailureType.CONNECTION_REFUSED: "Add connectivity precondition; consider retry with backoff",
    FailureType.COMMAND_NOT_FOUND: "Add tool availability precondition to κ(E) check",
    FailureType.IMAGE_PULL_FAILED: "Add image availability verification; provide image fallback",
    FailureType.PRECONDITION_FAILED: "Review environment compatibility; probe κ(E) before execution",
    FailureType.VERIFICATION_FAILED: "Strengthen success criteria; add more verification signals",
    FailureType.UNKNOWN: "Inspect raw output; consider adding more specific error patterns",
}


def _classify_message(text: str) -> FailureType:
    """Match a raw message against known failure patterns."""
    lower = text.lower()
    for patterns, ftype in _PATTERN_MAP:
        if any(p in lower for p in patterns):
            return ftype
    return FailureType.UNKNOWN


# ---------------------------------------------------------------------------
# Signature extraction from execution artefacts
# ---------------------------------------------------------------------------


def extract_signatures_from_preconditions(
    preconditions: list[VerificationResult],
) -> list[FailureSignature]:
    """Extract failure signatures from precondition check results."""
    sigs: list[FailureSignature] = []
    for check in preconditions:
        if not check.passed:
            raw_msg = check.detail or check.raw.stderr or check.raw.stdout
            ftype = _classify_message(raw_msg)
            if ftype == FailureType.UNKNOWN:
                ftype = FailureType.PRECONDITION_FAILED
            sigs.append(FailureSignature(
                failure_type=ftype,
                source="precondition",
                step_name=check.name,
                raw_message=raw_msg[:300],
                suggested_fix=_FIX_MAP.get(ftype, "Inspect raw output"),
            ))
    return sigs


def extract_signatures_from_actions(
    actions: list[CommandResult],
) -> list[FailureSignature]:
    """Extract failure signatures from command execution results."""
    sigs: list[FailureSignature] = []
    for action in actions:
        if action.returncode != 0:
            raw_msg = action.stderr or action.stdout
            ftype = _classify_message(raw_msg)
            sigs.append(FailureSignature(
                failure_type=ftype,
                source="action",
                step_name=action.command[:80],
                raw_message=raw_msg[:300],
                suggested_fix=_FIX_MAP.get(ftype, "Inspect raw output"),
            ))
    return sigs


def extract_signatures_from_verifications(
    checks: list[VerificationResult],
) -> list[FailureSignature]:
    """Extract failure signatures from success criteria results."""
    sigs: list[FailureSignature] = []
    for check in checks:
        if not check.passed:
            raw_msg = check.detail or check.raw.stderr or check.raw.stdout
            ftype = _classify_message(raw_msg)
            if ftype == FailureType.UNKNOWN:
                ftype = FailureType.VERIFICATION_FAILED
            sigs.append(FailureSignature(
                failure_type=ftype,
                source="verification",
                step_name=check.name,
                raw_message=raw_msg[:300],
                suggested_fix=_FIX_MAP.get(ftype, "Inspect raw output"),
            ))
    return sigs


def extract_gate_signature(block_reasons: list[str]) -> list[FailureSignature]:
    """Extract failure signatures from policy gate block reasons."""
    sigs: list[FailureSignature] = []
    for reason in block_reasons:
        sigs.append(FailureSignature(
            failure_type=FailureType.POLICY_BLOCKED,
            source="gate",
            step_name="policy_gate",
            raw_message=reason[:300],
            suggested_fix=_FIX_MAP[FailureType.POLICY_BLOCKED],
        ))
    return sigs
