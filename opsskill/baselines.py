"""Baseline and ablation implementations for OpsSkill experiment comparison.

Baselines:
  B1 - Direct Command Generation: raw kubectl from task description
  B2 - ReAct-style Agent: observe-reason-act loop
  B3 - Reflexion-style Agent: ReAct + retry with reflection
  B4 - Template Retrieval: skill bank without safety layers
  B5 - OpsSkill Full System: typed IR + policy gate + hidden verifier

Ablations:
  A1 - No Typed Skill IR (equivalent to B1)
  A2 - No Hidden Verification (skip success_criteria)
  A3 - No Policy Gate (execute regardless of risk level)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .remote import CommandResult, RemoteK8sRunner
from .skill_schema import ClusterConfig, SkillSpec
from .verifier import SkillVerifier, build_verification_judge
from .workflow import ExecutionReport, SkillExecutor

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TaskCard:
    """Defines an experiment task to be solved by each method."""

    name: str
    intent: str
    fault_domain: str
    task_family: str
    namespace: str
    workload: str
    expected_outcome: str
    opsskill_skill: str
    hidden_checks: list[dict[str, str]]
    task_type: str = "read-only"

    @classmethod
    def from_file(cls, path: str | Path) -> TaskCard:
        with Path(path).open("r", encoding="utf-8") as fh:
            d = yaml.safe_load(fh) or {}
        return cls(
            name=d["name"],
            intent=d["intent"],
            fault_domain=d["fault_domain"],
            task_family=d["task_family"],
            namespace=d.get("namespace", "opsskill-exp"),
            workload=d.get("workload", "demo-app"),
            expected_outcome=d.get("expected_outcome", ""),
            opsskill_skill=d["opsskill_skill"],
            hidden_checks=d.get("hidden_checks", []),
            task_type=d.get("task_type", "read-only"),
        )


@dataclass(slots=True)
class TrialResult:
    """Unified result format collected from every method on every task."""

    method: str
    task_name: str
    fault_domain: str
    task_family: str

    # Primary metrics
    task_success: bool
    hidden_pass: bool
    unsafe_actions: int
    rollback_available: bool
    rollback_triggered: bool

    # Secondary metrics
    tool_calls: int
    wall_time: float
    precondition_checked: bool
    verification_formal: bool

    # Raw data
    commands: list[dict[str, Any]] = field(default_factory=list)
    hidden_results: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0
    notes: str = ""


# ---------------------------------------------------------------------------
# Hidden verification (applied uniformly to every method)
# ---------------------------------------------------------------------------


def run_hidden_checks(
    task: TaskCard, runner: RemoteK8sRunner
) -> tuple[bool, list[dict[str, Any]]]:
    """Execute the task-level hidden verification checks.

    These are independent of what the method reports internally and serve
    as the ground truth for *hidden verification pass rate*.
    """
    results: list[dict[str, Any]] = []
    all_pass = True
    for check in task.hidden_checks:
        raw = runner.run(check["command"], check=False)
        passed = raw.returncode == 0
        if passed and check.get("expect_stdout_contains"):
            passed = check["expect_stdout_contains"] in raw.stdout
        results.append(
            {
                "name": check["name"],
                "passed": passed,
                "stdout": raw.stdout[:500],
                "returncode": raw.returncode,
            }
        )
        if not passed:
            all_pass = False
    return all_pass, results


# ---------------------------------------------------------------------------
# B1 — Direct Command Generation
# ---------------------------------------------------------------------------

_INTENT_COMMAND_MAP: dict[str, list[str]] = {
    # detection
    "detect+metric": [
        "kubectl -n {ns} top pods 2>/dev/null || kubectl -n {ns} get pods -o wide"
    ],
    "detect+event": [
        "kubectl -n {ns} get events --sort-by=.lastTimestamp"
    ],
    "detect+config": [
        "kubectl -n {ns} get all -o wide"
    ],
    # diagnosis
    "diagnose+state": [
        "kubectl -n {ns} describe pods"
    ],
    "diagnose+root": [
        "kubectl -n {ns} logs -l app={wl} --tail=50 2>/dev/null; "
        "kubectl -n {ns} get events --field-selector type=Warning"
    ],
    # recovery
    "recover+restart": [
        "kubectl -n {ns} rollout restart deployment/{wl}"
    ],
    "verify+recovery": [
        "kubectl -n {ns} get pods -o wide"
    ],
}


def _intent_to_commands(intent: str, ns: str, workload: str) -> list[str]:
    """Map a task intent string to raw kubectl commands (simulates LLM output)."""
    il = intent.lower()
    for key, cmds in _INTENT_COMMAND_MAP.items():
        parts = key.split("+")
        if all(p in il for p in parts):
            return [c.format(ns=ns, wl=workload) for c in cmds]
    # Fallback: generic pod listing
    return [f"kubectl -n {ns} get pods -o wide"]


class DirectCommandBaseline:
    """B1: Map task intent to raw kubectl commands — no safety structure."""

    name = "B1-direct"

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()
        raw_cmds = _intent_to_commands(task.intent, task.namespace, task.workload)

        cmd_results: list[dict[str, Any]] = []
        success = True
        for cmd in raw_cmds:
            r = runner.run(cmd, check=False)
            cmd_results.append(
                {
                    "command": cmd,
                    "returncode": r.returncode,
                    "stdout": r.stdout[:500],
                    "stderr": r.stderr[:200],
                }
            )
            if r.returncode != 0:
                success = False

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)
        act_ratio = sum(1 for c in cmd_results if c["returncode"] == 0) / max(len(cmd_results), 1)
        score = 0.25 * act_ratio  # only action component

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=success,
            hidden_pass=hidden_pass,
            unsafe_actions=0,
            rollback_available=False,
            rollback_triggered=False,
            tool_calls=len(raw_cmds),
            wall_time=wall,
            precondition_checked=False,
            verification_formal=False,
            commands=cmd_results,
            hidden_results=hidden_res,
            score=score,
            notes="Direct command generation without safety structure",
        )


# ---------------------------------------------------------------------------
# B2 — ReAct-style Agent
# ---------------------------------------------------------------------------


class ReActBaseline:
    """B2: Observe → Reason → Act → Observe-result (no typed IR)."""

    name = "B2-react"

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()
        cmd_results: list[dict[str, Any]] = []

        # --- observe ---
        obs = runner.run(
            f"kubectl -n {task.namespace} get pods,events --no-headers 2>/dev/null | head -30",
            check=False,
        )
        cmd_results.append({"phase": "observe", "command": obs.command, "returncode": obs.returncode, "stdout": obs.stdout[:500]})

        # --- reason + act ---
        actions = self._select_actions(task)
        act_ok = True
        for cmd in actions:
            r = runner.run(cmd, check=False)
            cmd_results.append({"phase": "act", "command": cmd, "returncode": r.returncode, "stdout": r.stdout[:500], "stderr": r.stderr[:200]})
            if r.returncode != 0:
                act_ok = False

        # --- observe result ---
        chk = runner.run(f"kubectl -n {task.namespace} get pods -o wide", check=False)
        cmd_results.append({"phase": "observe-result", "command": chk.command, "returncode": chk.returncode, "stdout": chk.stdout[:500]})

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)
        act_ratio = sum(1 for c in cmd_results if c.get("phase") == "act" and c["returncode"] == 0) / max(len(actions), 1)
        score = 0.25 * act_ratio + 0.15 * (1.0 if chk.returncode == 0 else 0.0)

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=act_ok,
            hidden_pass=hidden_pass,
            unsafe_actions=0,
            rollback_available=False,
            rollback_triggered=False,
            tool_calls=len(cmd_results),
            wall_time=wall,
            precondition_checked=False,
            verification_formal=False,
            commands=cmd_results,
            hidden_results=hidden_res,
            score=score,
            notes="ReAct observe-act loop without formal verification",
        )

    # -- heuristic action selection --
    @staticmethod
    def _select_actions(task: TaskCard) -> list[str]:
        ns, wl = task.namespace, task.workload
        il = task.intent.lower()
        if "event" in il and "detect" in il:
            return [f"kubectl -n {ns} get events --field-selector type=Warning --sort-by=.lastTimestamp"]
        if "detect" in il or "metric" in il:
            return [
                f"kubectl -n {ns} get pods -o custom-columns="
                "NAME:.metadata.name,READY:.status.containerStatuses[*].ready,"
                "RESTARTS:.status.containerStatuses[*].restartCount,PHASE:.status.phase"
            ]
        if "diagnos" in il or "state" in il:
            return [f"kubectl -n {ns} describe pods -l app={wl} | head -60"]
        if "root" in il or "candidate" in il:
            return [
                f"kubectl -n {ns} get pods -o jsonpath="
                "'{range .items[*]}{.metadata.name}\\t{.status.phase}\\t"
                "{range .status.containerStatuses[*]}{.state.waiting.reason} "
                "{.lastState.terminated.reason} {end}\\n{end}'"
            ]
        if "recover" in il or "restart" in il:
            return [f"kubectl -n {ns} rollout restart deployment/{wl}"]
        if "verif" in il and "recover" in il:
            return [f"kubectl -n {ns} get deployments,pods,svc -o wide"]
        if "config" in il or "correlat" in il:
            return [f"kubectl -n {ns} get all -o wide"]
        return [f"kubectl -n {ns} get pods -o wide"]


# ---------------------------------------------------------------------------
# B3 — Reflexion-style Agent
# ---------------------------------------------------------------------------


class ReflexionBaseline:
    """B3: ReAct + retry-with-reflection on failure."""

    name = "B3-reflexion"

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()
        cmd_results: list[dict[str, Any]] = []

        # --- initial observe ---
        obs = runner.run(
            f"kubectl -n {task.namespace} get pods,events --no-headers 2>/dev/null | head -30",
            check=False,
        )
        cmd_results.append({"phase": "observe", "command": obs.command, "returncode": obs.returncode, "stdout": obs.stdout[:500]})

        # --- act with retries ---
        variants = self._action_variants(task)
        success = False
        attempts = 0
        for v in variants[: self.max_retries + 1]:
            attempts += 1
            r = runner.run(v, check=False)
            cmd_results.append({"phase": f"act-{attempts}", "command": v, "returncode": r.returncode, "stdout": r.stdout[:500], "stderr": r.stderr[:200]})
            if r.returncode == 0:
                success = True
                break
            cmd_results.append({"phase": f"reflect-{attempts}", "command": f"# reflect: exit {r.returncode}, try next variant", "returncode": -1, "stdout": ""})

        # --- final observe ---
        chk = runner.run(f"kubectl -n {task.namespace} get pods -o wide", check=False)
        cmd_results.append({"phase": "final-observe", "command": chk.command, "returncode": chk.returncode, "stdout": chk.stdout[:500]})

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)
        score = 0.25 * (1.0 if success else 0.0) + 0.15 * (1.0 if chk.returncode == 0 else 0.0)

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=success,
            hidden_pass=hidden_pass,
            unsafe_actions=0,
            rollback_available=False,
            rollback_triggered=False,
            tool_calls=sum(1 for c in cmd_results if not c.get("command", "").startswith("#")),
            wall_time=wall,
            precondition_checked=False,
            verification_formal=False,
            commands=cmd_results,
            hidden_results=hidden_res,
            score=score,
            notes=f"Reflexion with {attempts} attempt(s)",
        )

    @staticmethod
    def _action_variants(task: TaskCard) -> list[str]:
        ns, wl = task.namespace, task.workload
        il = task.intent.lower()
        if "event" in il and "detect" in il:
            return [
                f"kubectl -n {ns} get events --field-selector type=Warning --sort-by=.lastTimestamp",
                f"kubectl -n {ns} get events --sort-by=.lastTimestamp",
                f"kubectl -n {ns} get events",
            ]
        if "detect" in il or "metric" in il:
            return [
                f"kubectl -n {ns} get pods -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[*].ready,RESTARTS:.status.containerStatuses[*].restartCount,PHASE:.status.phase",
                f"kubectl -n {ns} get pods -o wide",
                f"kubectl -n {ns} get pods",
            ]
        if "diagnos" in il or "state" in il:
            return [
                f"kubectl -n {ns} describe pods -l app={wl} | head -60",
                f"kubectl -n {ns} describe pods | head -60",
                f"kubectl -n {ns} get pods -o yaml | head -80",
            ]
        if "root" in il or "candidate" in il:
            return [
                f"kubectl -n {ns} get pods -o jsonpath='{{range .items[*]}}{{.metadata.name}}\\t{{.status.phase}}\\t{{range .status.containerStatuses[*]}}{{.state.waiting.reason}} {{.lastState.terminated.reason}} {{end}}\\n{{end}}'",
                f"kubectl -n {ns} describe pods | grep -A5 'State\\|Reason'",
                f"kubectl -n {ns} get pods -o wide",
            ]
        if "recover" in il or "restart" in il:
            return [
                f"kubectl -n {ns} rollout restart deployment/{wl}",
                f"kubectl -n {ns} delete pods -l app={wl}",
                f"kubectl -n {ns} scale deployment/{wl} --replicas=0 && sleep 3 && kubectl -n {ns} scale deployment/{wl} --replicas=1",
            ]
        if "verif" in il and "recover" in il:
            return [
                f"kubectl -n {ns} get deployments,pods,svc -o wide",
                f"kubectl -n {ns} get deployments -o wide",
                f"kubectl -n {ns} get pods",
            ]
        if "config" in il or "correlat" in il:
            return [
                f"kubectl -n {ns} get all -o wide",
                f"kubectl -n {ns} get pods,svc,deploy -o wide",
                f"kubectl -n {ns} get pods",
            ]
        return [f"kubectl -n {ns} get pods -o wide"]


# ---------------------------------------------------------------------------
# B4 — Template / Runbook Retrieval
# ---------------------------------------------------------------------------


class TemplateRetrievalBaseline:
    """B4: Use matching skill from bank, but skip safety layers.

    Executes the skill's actions directly — no precondition check,
    no success_criteria verification, no policy gate.
    """

    name = "B4-template"

    def __init__(self, project_root: str | Path = "."):
        self.project_root = Path(project_root)

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()

        skill_path = self.project_root / task.opsskill_skill
        skill = SkillSpec.from_file(skill_path)

        cmd_results: list[dict[str, Any]] = []
        success = True
        for action in skill.actions:
            r = runner.run(action.command, check=False)
            cmd_results.append(
                {
                    "command": action.command,
                    "returncode": r.returncode,
                    "stdout": r.stdout[:500],
                    "stderr": r.stderr[:200],
                }
            )
            if r.returncode != 0:
                success = False

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)
        act_ratio = sum(1 for c in cmd_results if c["returncode"] == 0) / max(len(cmd_results), 1)
        score = 0.25 * act_ratio  # no precondition or verification components

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=success,
            hidden_pass=hidden_pass,
            unsafe_actions=0,
            rollback_available=bool(skill.rollback),
            rollback_triggered=False,
            tool_calls=len(skill.actions),
            wall_time=wall,
            precondition_checked=False,
            verification_formal=False,
            commands=cmd_results,
            hidden_results=hidden_res,
            score=score,
            notes="Template retrieval without safety infrastructure",
        )


# ---------------------------------------------------------------------------
# B5 — OpsSkill Full System
# ---------------------------------------------------------------------------


class OpsSkillFullBaseline:
    """B5: Full OpsSkill pipeline — precondition → action → verification → rollback."""

    name = "B5-opsskill"

    def __init__(
        self,
        cluster: ClusterConfig,
        project_root: str | Path = ".",
        verifier: str = "heuristic",
    ):
        self.cluster = cluster
        self.project_root = Path(project_root)
        self._executor = SkillExecutor(cluster, verifier=verifier)

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()

        skill_path = self.project_root / task.opsskill_skill
        skill = SkillSpec.from_file(skill_path)

        report = self._executor.run(skill, execute_actions=True)

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)

        cmd_results = [
            {"command": a.command, "returncode": a.returncode, "stdout": a.stdout[:500]}
            for a in report.actions
        ]

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=report.succeeded,
            hidden_pass=hidden_pass,
            unsafe_actions=0,
            rollback_available=bool(skill.rollback),
            rollback_triggered=bool(report.rollback),
            tool_calls=len(report.preconditions) + len(report.actions) + len(report.success_criteria),
            wall_time=wall,
            precondition_checked=bool(report.preconditions),
            verification_formal=bool(report.success_criteria),
            commands=cmd_results,
            hidden_results=hidden_res,
            score=report.score,
            notes="Full OpsSkill pipeline",
        )


# ---------------------------------------------------------------------------
# Ablation variants
# ---------------------------------------------------------------------------


class AblationNoIR:
    """A1: Remove typed skill IR — equivalent to B1 direct command."""

    name = "A1-no-ir"

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        inner = DirectCommandBaseline()
        result = inner.execute(task, runner)
        result.method = self.name
        result.notes = "Ablation: no typed skill IR (≈ B1 direct command)"
        return result


class AblationNoHiddenVerify:
    """A2: Run skill with preconditions but skip success_criteria."""

    name = "A2-no-hidden-verify"

    def __init__(self, cluster: ClusterConfig, project_root: str | Path = "."):
        self.cluster = cluster
        self.project_root = Path(project_root)

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()

        skill_path = self.project_root / task.opsskill_skill
        skill = SkillSpec.from_file(skill_path)

        verifier = SkillVerifier(runner, judge=build_verification_judge("heuristic"))
        precond = verifier.verify(skill.preconditions)
        precond_ok = all(r.passed for r in precond)

        cmd_results: list[dict[str, Any]] = []
        act_ok = True
        if precond_ok:
            for action in skill.actions:
                r = runner.run(action.command, check=False)
                cmd_results.append({"command": action.command, "returncode": r.returncode, "stdout": r.stdout[:500]})
                if r.returncode != 0:
                    act_ok = False
        else:
            act_ok = False

        # success_criteria intentionally skipped (the ablation)

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)

        pre_ratio = sum(1 for r in precond if r.passed) / max(len(precond), 1)
        act_ratio = sum(1 for c in cmd_results if c["returncode"] == 0) / max(len(cmd_results), 1) if cmd_results else 0.0
        score = 0.35 * pre_ratio + 0.25 * act_ratio  # no verification component

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=act_ok and precond_ok,
            hidden_pass=hidden_pass,
            unsafe_actions=0,
            rollback_available=bool(skill.rollback),
            rollback_triggered=False,
            tool_calls=len(precond) + len(cmd_results),
            wall_time=wall,
            precondition_checked=True,
            verification_formal=False,
            commands=cmd_results,
            hidden_results=hidden_res,
            score=score,
            notes="Ablation: success_criteria verification removed",
        )


class AblationNoPolicyGate:
    """A3: Full pipeline but no risk-level policy gate — always execute."""

    name = "A3-no-policy-gate"

    def __init__(self, cluster: ClusterConfig, project_root: str | Path = "."):
        self.cluster = cluster
        self.project_root = Path(project_root)
        self._executor = SkillExecutor(cluster)

    def execute(self, task: TaskCard, runner: RemoteK8sRunner) -> TrialResult:
        t0 = time.monotonic()

        skill_path = self.project_root / task.opsskill_skill
        skill = SkillSpec.from_file(skill_path)
        metadata = skill.metadata or {}

        report = self._executor.run(skill, execute_actions=True, allow_mutation=True)  # bypass policy gate

        wall = time.monotonic() - t0
        hidden_pass, hidden_res = run_hidden_checks(task, runner)

        is_risky = metadata.get("category") == "action" or str(metadata.get("risk_level", "")) in ("medium", "high")
        unsafe = 1 if is_risky else 0

        cmd_results = [
            {"command": a.command, "returncode": a.returncode, "stdout": a.stdout[:500]}
            for a in report.actions
        ]

        return TrialResult(
            method=self.name,
            task_name=task.name,
            fault_domain=task.fault_domain,
            task_family=task.task_family,
            task_success=report.succeeded,
            hidden_pass=hidden_pass,
            unsafe_actions=unsafe,
            rollback_available=bool(skill.rollback),
            rollback_triggered=bool(report.rollback),
            tool_calls=len(report.preconditions) + len(report.actions) + len(report.success_criteria),
            wall_time=wall,
            precondition_checked=bool(report.preconditions),
            verification_formal=bool(report.success_criteria),
            commands=cmd_results,
            hidden_results=hidden_res,
            score=report.score,
            notes=f"Ablation: no policy gate (unsafe_actions={unsafe})",
        )


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def build_all_methods(
    cluster: ClusterConfig,
    project_root: str | Path = ".",
) -> dict[str, Any]:
    """Return a dict  name → method instance  for every baseline + ablation."""
    root = Path(project_root)
    return {
        "B1-direct": DirectCommandBaseline(),
        "B2-react": ReActBaseline(),
        "B3-reflexion": ReflexionBaseline(max_retries=2),
        "B4-template": TemplateRetrievalBaseline(project_root=root),
        "B5-opsskill": OpsSkillFullBaseline(cluster, project_root=root),
        "A1-no-ir": AblationNoIR(),
        "A2-no-hidden-verify": AblationNoHiddenVerify(cluster, project_root=root),
        "A3-no-policy-gate": AblationNoPolicyGate(cluster, project_root=root),
    }
