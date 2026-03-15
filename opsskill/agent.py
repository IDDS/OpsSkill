from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .planner import HeuristicPlanningPolicy, OpenAICompatiblePlanningPolicy
from .policy_gate import PolicyConstraints
from .skill_schema import ClusterConfig, SkillSpec
from .workflow import ExecutionReport, SkillExecutor


@dataclass(slots=True)
class RegisteredSkill:
    path: str
    spec: SkillSpec
    stage: str
    category: str
    risk_level: str
    benchmark_tags: list[str] = field(default_factory=list)
    mutability: str = "unknown"


@dataclass(slots=True)
class AgentStep:
    stage: str
    skill_path: str
    skill_name: str
    selected_score: float
    executed: bool
    report: ExecutionReport
    blocked: bool = False


@dataclass(slots=True)
class AgentRunReport:
    task_summary: str
    stages: list[str]
    planner_requested: str = "heuristic"
    planner_used: str = "heuristic"
    planner_fallback_reason: str | None = None
    steps: list[AgentStep] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return bool(self.steps) and all(step.report.succeeded for step in self.steps if step.executed)

    @property
    def score(self) -> float:
        executed_steps = [step for step in self.steps if step.executed]
        if not executed_steps:
            return 0.0
        return sum(step.report.score for step in executed_steps) / len(executed_steps)

    @property
    def hidden_succeeded(self) -> bool:
        """True iff all executed skills pass hidden verification."""
        executed = [step for step in self.steps if step.executed]
        return bool(executed) and all(step.report.hidden_succeeded for step in executed)

    @property
    def blocked_count(self) -> int:
        """Number of skills blocked by the policy gate."""
        return sum(1 for step in self.steps if step.blocked)

    @property
    def false_positive_gap(self) -> float:
        """Average Δ_fp across all executed skills."""
        executed = [step for step in self.steps if step.executed]
        if not executed:
            return 0.0
        return sum(step.report.false_positive_gap for step in executed) / len(executed)


class SkillRegistry:
    def __init__(self, skills_root: str | Path):
        self.skills_root = Path(skills_root)

    def load(self) -> list[RegisteredSkill]:
        registered: list[RegisteredSkill] = []
        for path in sorted(self.skills_root.rglob("*.yaml")):
            spec = SkillSpec.from_file(path)
            metadata = spec.metadata or {}
            benchmark = metadata.get("benchmark", {})
            registered.append(
                RegisteredSkill(
                    path=str(path),
                    spec=spec,
                    stage=str(metadata.get("stage", "unknown")),
                    category=str(metadata.get("category", "unknown")),
                    risk_level=str(metadata.get("risk_level", "unknown")),
                    benchmark_tags=[str(item) for item in benchmark.get("benchmark_tags", [])],
                    mutability=str(benchmark.get("mutability", metadata.get("category", "unknown"))),
                )
            )
        return registered

class ManagerAgent:
    """Hierarchical Skill Orchestration Agent — Section 4.2.4.

    The agent iterates through stages (detection → diagnosis → recovery),
    selects skills via the planner π, and delegates execution to
    SkillExecutor which implements the full algorithm pipeline including
    κ(E) probing, B(S,E) risk budget, g_ψ policy gate, V_hid, and σ extraction.
    """

    def __init__(
        self,
        cluster: ClusterConfig,
        skills_root: str | Path = "skills",
        planner: str = "heuristic",
        planner_model: str = "gpt-5.4",
        planner_base_url: str = "https://api.openai.com/v1",
        planner_api_key_env: str = "OPENAI_API_KEY",
        verifier: str = "heuristic",
        verifier_model: str = "gpt-5.4",
        verifier_base_url: str = "https://api.openai.com/v1",
        verifier_api_key_env: str = "OPENAI_API_KEY",
        constraints: PolicyConstraints | None = None,
    ):
        self.constraints = constraints or PolicyConstraints()
        self.executor = SkillExecutor(
            cluster,
            verifier=verifier,
            verifier_model=verifier_model,
            verifier_base_url=verifier_base_url,
            verifier_api_key_env=verifier_api_key_env,
            constraints=self.constraints,
        )
        self.registry = SkillRegistry(skills_root)
        self.planner_name = planner
        self.policy = self._build_policy(planner, planner_model, planner_base_url, planner_api_key_env)

    def run(
        self,
        task_card_path: str | Path | None = None,
        stages: list[str] | None = None,
        max_skills_per_stage: int = 1,
        allow_mutation: bool = False,
        execute_actions: bool = True,
    ) -> AgentRunReport:
        task_card = _load_task_card(task_card_path)
        task_summary = _task_text(task_card) if task_card else "No task card provided"
        chosen_stages = stages or ["detection", "diagnosis", "recovery"]
        skills = self.registry.load()
        planning = self.policy.select(skills, task_card, chosen_stages, max_skills_per_stage, allow_mutation)

        report = AgentRunReport(
            task_summary=task_summary,
            stages=chosen_stages,
            planner_requested=self.planner_name,
            planner_used=planning.planner_used,
            planner_fallback_reason=planning.fallback_reason,
            skipped_skills=planning.skipped,
        )
        for skill, score in planning.selected:
            # Run the full algorithm pipeline via SkillExecutor
            # The executor handles κ(E), B(S,E), g_ψ, V_vis, V_hid, σ internally
            skill_report = self.executor.run(
                skill.spec,
                execute_actions=execute_actions,
                run_hidden=True,
                allow_mutation=allow_mutation,
            )

            was_blocked = skill_report.was_blocked
            was_executed = execute_actions and not was_blocked

            report.steps.append(
                AgentStep(
                    stage=skill.stage,
                    skill_path=skill.path,
                    skill_name=skill.spec.name,
                    selected_score=score,
                    executed=was_executed,
                    report=skill_report,
                    blocked=was_blocked,
                )
            )
        return report

    def _build_policy(
        self,
        planner: str,
        planner_model: str,
        planner_base_url: str,
        planner_api_key_env: str,
    ) -> HeuristicPlanningPolicy | OpenAICompatiblePlanningPolicy:
        if planner == "llm":
            return OpenAICompatiblePlanningPolicy(
                model=planner_model,
                base_url=planner_base_url,
                api_key_env=planner_api_key_env,
            )
        return HeuristicPlanningPolicy()


def _load_task_card(task_card_path: str | Path | None) -> dict[str, Any]:
    if not task_card_path:
        return {}
    with Path(task_card_path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _task_text(task_card: dict[str, Any]) -> str:
    values = [
        str(task_card.get("name", "")),
        str(task_card.get("intent", "")),
        str(task_card.get("diagnosis", "")),
        str(task_card.get("workload", "")),
        str(task_card.get("namespace", "")),
        str(task_card.get("severity", "")),
    ]
    return " ".join(item for item in values if item).lower()


def _is_mutating(skill: RegisteredSkill) -> bool:
    return skill.mutability == "mutating" or skill.category == "action"
