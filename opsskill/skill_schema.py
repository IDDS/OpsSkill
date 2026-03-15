from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class SkillValidationError(ValueError):
    pass


@dataclass(slots=True)
class VerificationSpec:
    name: str
    command: str
    expect_exit_code: int = 0
    expect_stdout_contains: str | None = None


@dataclass(slots=True)
class ActionSpec:
    name: str
    command: str
    on_failure: str = "abort"


@dataclass(slots=True)
class ClusterConfig:
    jump_host: str
    target_host: str
    namespace: str = "opsskill-sandbox"
    kube_context: str | None = None
    ssh_options: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> "ClusterConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        required = ["jump_host", "target_host"]
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise SkillValidationError(f"Missing cluster config keys: {', '.join(missing)}")
        return cls(
            jump_host=payload["jump_host"],
            target_host=payload["target_host"],
            namespace=payload.get("namespace", "opsskill-sandbox"),
            kube_context=payload.get("kube_context"),
            ssh_options=payload.get("ssh_options", []),
        )


@dataclass(slots=True)
class SkillSpec:
    version: str
    name: str
    intent: str
    namespace: str
    preconditions: list[VerificationSpec]
    actions: list[ActionSpec]
    success_criteria: list[VerificationSpec]
    rollback: list[ActionSpec]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "SkillSpec":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SkillSpec":
        required = ["version", "name", "intent", "namespace", "actions", "success_criteria"]
        missing = [key for key in required if key not in payload or payload[key] in (None, "")]
        if missing:
            raise SkillValidationError(f"Missing required skill keys: {', '.join(missing)}")
        preconditions = [_verification_from_dict(item) for item in payload.get("preconditions", [])]
        actions = [_action_from_dict(item) for item in payload.get("actions", [])]
        success_criteria = [_verification_from_dict(item) for item in payload.get("success_criteria", [])]
        rollback = [_action_from_dict(item) for item in payload.get("rollback", [])]
        if not actions:
            raise SkillValidationError("Skill must define at least one action")
        if not success_criteria:
            raise SkillValidationError("Skill must define at least one success criterion")
        return cls(
            version=str(payload["version"]),
            name=str(payload["name"]),
            intent=str(payload["intent"]),
            namespace=str(payload["namespace"]),
            preconditions=preconditions,
            actions=actions,
            success_criteria=success_criteria,
            rollback=rollback,
            metadata=payload.get("metadata", {}),
        )


def _verification_from_dict(payload: dict[str, Any]) -> VerificationSpec:
    name = payload.get("name")
    command = payload.get("command")
    if not name or not command:
        raise SkillValidationError("Each verification item needs name and command")
    return VerificationSpec(
        name=str(name),
        command=str(command),
        expect_exit_code=int(payload.get("expect_exit_code", 0)),
        expect_stdout_contains=payload.get("expect_stdout_contains"),
    )


def _action_from_dict(payload: dict[str, Any]) -> ActionSpec:
    name = payload.get("name")
    command = payload.get("command")
    if not name or not command:
        raise SkillValidationError("Each action item needs name and command")
    return ActionSpec(
        name=str(name),
        command=str(command),
        on_failure=str(payload.get("on_failure", "abort")),
    )
