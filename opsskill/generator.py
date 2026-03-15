from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .llm import LLMConfig, OpenAICompatibleLLM
from .skill_schema import SkillSpec


def synthesize_skill(task_card: dict[str, Any]) -> dict[str, Any]:
    namespace = task_card.get("namespace", "opsskill-sandbox")
    workload = task_card.get("workload", "demo-app")
    diagnosis = task_card.get("diagnosis", "restart deployment to recover from transient failure")
    return {
        "version": "0.1",
        "name": task_card.get("name", f"recover-{workload}"),
        "intent": task_card.get("intent", diagnosis),
        "namespace": namespace,
        "metadata": {
            "source": "template-generator",
            "severity": task_card.get("severity", "medium"),
        },
        "preconditions": [
            {
                "name": "target deployment exists",
                "command": f"kubectl -n {namespace} get deployment {workload}",
            }
        ],
        "actions": [
            {
                "name": "rollout restart deployment",
                "command": f"kubectl -n {namespace} rollout restart deployment/{workload}",
                "on_failure": "rollback",
            }
        ],
        "success_criteria": [
            {
                "name": "deployment available",
                "command": f"kubectl -n {namespace} rollout status deployment/{workload} --timeout=120s",
                "expect_stdout_contains": "successfully rolled out",
            }
        ],
        "rollback": [
            {
                "name": "undo rollout",
                "command": f"kubectl -n {namespace} rollout undo deployment/{workload}",
            }
        ],
    }


class TemplateSkillGenerator:
    name = "template"

    def synthesize(self, task_card: dict[str, Any]) -> dict[str, Any]:
        return synthesize_skill(task_card)


class LLMSkillGenerator:
    name = "llm"

    def __init__(self, config: LLMConfig, fallback: TemplateSkillGenerator | None = None):
        self.client = OpenAICompatibleLLM(config)
        self.fallback = fallback or TemplateSkillGenerator()

    def synthesize(self, task_card: dict[str, Any]) -> dict[str, Any]:
        system_prompt = (
            "You are a safe DevOps skill compiler. Convert the task card into a valid OpsSkill JSON object. "
            "Return strict JSON with keys: version, name, intent, namespace, metadata, preconditions, actions, success_criteria, rollback. "
            "Prefer safe, namespace-scoped commands and include rollback for mutating actions."
        )
        try:
            payload = self.client.complete_json(system_prompt, {"task_card": task_card})
            payload.setdefault("metadata", {})
            payload["metadata"]["source"] = "llm-generator"
            SkillSpec.from_dict(payload)
            return payload
        except Exception:
            payload = self.fallback.synthesize(task_card)
            payload.setdefault("metadata", {})
            payload["metadata"]["source"] = "template-fallback"
            return payload


def build_generator(
    generator: str = "template",
    model: str = "gpt-5.4",
    base_url: str = "https://api.openai.com/v1",
    api_key_env: str = "OPENAI_API_KEY",
) -> TemplateSkillGenerator | LLMSkillGenerator:
    if generator == "llm":
        return LLMSkillGenerator(LLMConfig(model=model, base_url=base_url, api_key_env=api_key_env))
    return TemplateSkillGenerator()


def write_skill(
    task_card_path: str | Path,
    output_path: str | Path,
    generator: str = "template",
    model: str = "gpt-5.4",
    base_url: str = "https://api.openai.com/v1",
    api_key_env: str = "OPENAI_API_KEY",
) -> SkillSpec:
    with Path(task_card_path).open("r", encoding="utf-8") as handle:
        task_card = yaml.safe_load(handle) or {}
    skill_payload = build_generator(generator, model, base_url, api_key_env).synthesize(task_card)
    with Path(output_path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(skill_payload, handle, sort_keys=False, allow_unicode=True)
    return SkillSpec.from_dict(skill_payload)
