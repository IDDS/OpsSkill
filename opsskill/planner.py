from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent import RegisteredSkill


@dataclass(slots=True)
class PlanningOutcome:
    selected: list[tuple[RegisteredSkill, float]]
    skipped: list[str] = field(default_factory=list)
    planner_used: str = "heuristic"
    fallback_reason: str | None = None


class HeuristicPlanningPolicy:
    name = "heuristic"

    def select(
        self,
        skills: list[RegisteredSkill],
        task_card: dict[str, Any],
        stages: list[str],
        max_skills_per_stage: int,
        allow_mutation: bool,
    ) -> PlanningOutcome:
        task_text = _task_text(task_card)
        selected: list[tuple[RegisteredSkill, float]] = []
        skipped: list[str] = []

        for stage in stages:
            stage_skills = [skill for skill in skills if skill.stage == stage]
            ranked = sorted(
                ((skill, _score_skill(skill, task_text, stage)) for skill in stage_skills),
                key=lambda item: item[1],
                reverse=True,
            )
            stage_selected = 0
            for skill, score in ranked:
                if stage_selected >= max_skills_per_stage:
                    break
                if not allow_mutation and _is_mutating(skill):
                    skipped.append(skill.path)
                    continue
                selected.append((skill, score))
                stage_selected += 1
        return PlanningOutcome(selected=selected, skipped=skipped, planner_used=self.name)


class OpenAICompatiblePlanningPolicy:
    name = "llm"

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: float = 45.0,
        fallback_policy: HeuristicPlanningPolicy | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.fallback_policy = fallback_policy or HeuristicPlanningPolicy()

    def select(
        self,
        skills: list[RegisteredSkill],
        task_card: dict[str, Any],
        stages: list[str],
        max_skills_per_stage: int,
        allow_mutation: bool,
    ) -> PlanningOutcome:
        try:
            api_key = os.environ.get(self.api_key_env)
            if not api_key:
                raise RuntimeError(f"Missing API key in env var {self.api_key_env}")
            payload = self._build_request(skills, task_card, stages, max_skills_per_stage, allow_mutation)
            response = self._call_api(payload, api_key)
            outcome = self._parse_response(response, skills, stages, max_skills_per_stage, allow_mutation)
            outcome.planner_used = self.name
            return outcome
        except Exception as exc:
            fallback = self.fallback_policy.select(skills, task_card, stages, max_skills_per_stage, allow_mutation)
            fallback.planner_used = fallback.planner_used
            fallback.fallback_reason = str(exc)
            return fallback

    def _build_request(
        self,
        skills: list[RegisteredSkill],
        task_card: dict[str, Any],
        stages: list[str],
        max_skills_per_stage: int,
        allow_mutation: bool,
    ) -> dict[str, Any]:
        candidates = []
        for skill in skills:
            candidates.append(
                {
                    "path": skill.path,
                    "name": skill.spec.name,
                    "intent": skill.spec.intent,
                    "stage": skill.stage,
                    "category": skill.category,
                    "risk_level": skill.risk_level,
                    "mutability": skill.mutability,
                    "benchmark_tags": skill.benchmark_tags,
                }
            )
        system_prompt = (
            "You are a safe operations planning agent. Select the most relevant skills for the given task card. "
            "Prefer stage-consistent skills, prefer paper-minimal-set skills when relevant, and avoid mutating skills unless allowed. "
            "Return strict JSON with a top-level key 'selected' whose value is a list of objects with keys: path and score."
        )
        user_payload = {
            "task_card": task_card,
            "stages": stages,
            "max_skills_per_stage": max_skills_per_stage,
            "allow_mutation": allow_mutation,
            "candidates": candidates,
        }
        return {
            "model": self.model,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }

    def _call_api(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Planner API HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Planner API connection failed: {exc.reason}") from exc

    def _parse_response(
        self,
        response: dict[str, Any],
        skills: list[RegisteredSkill],
        stages: list[str],
        max_skills_per_stage: int,
        allow_mutation: bool,
    ) -> PlanningOutcome:
        content = response["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        selected_payload = parsed.get("selected", [])
        by_path = {skill.path: skill for skill in skills}
        selected: list[tuple[RegisteredSkill, float]] = []
        skipped: list[str] = []
        stage_counts = {stage: 0 for stage in stages}

        for item in selected_payload:
            path = item.get("path")
            score = float(item.get("score", 0.0))
            skill = by_path.get(path)
            if not skill or skill.stage not in stages:
                continue
            if stage_counts[skill.stage] >= max_skills_per_stage:
                continue
            if not allow_mutation and _is_mutating(skill):
                skipped.append(skill.path)
                continue
            selected.append((skill, score))
            stage_counts[skill.stage] += 1

        if not selected:
            raise RuntimeError("LLM planner returned no usable skills")
        return PlanningOutcome(selected=selected, skipped=skipped, planner_used=self.name)



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



def _score_skill(skill: RegisteredSkill, task_text: str, stage: str) -> float:
    tokens = set(task_text.replace("-", " ").replace("_", " ").split())
    skill_text = " ".join(
        [
            skill.spec.name.lower(),
            skill.spec.intent.lower(),
            skill.stage.lower(),
            skill.category.lower(),
            " ".join(skill.benchmark_tags).lower(),
        ]
    )
    skill_tokens = set(skill_text.replace("-", " ").replace("_", " ").split())
    overlap = len(tokens & skill_tokens)
    stage_bonus = 3.0 if skill.stage == stage else 0.0
    paper_bonus = 1.5 if "paper-minimal-set" in skill.benchmark_tags else 0.0
    mutability_penalty = -0.5 if _is_mutating(skill) else 0.5
    return stage_bonus + paper_bonus + mutability_penalty + overlap



def _is_mutating(skill: RegisteredSkill) -> bool:
    return skill.mutability == "mutating" or skill.category == "action"
