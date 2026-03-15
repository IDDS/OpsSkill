from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .llm import LLMConfig, OpenAICompatibleLLM
from .remote import CommandResult, RemoteK8sRunner
from .skill_schema import VerificationSpec


@dataclass(slots=True)
class VerificationResult:
    name: str
    passed: bool
    detail: str
    raw: CommandResult
    agent_rationale: str | None = None
    agent_verdict: str | None = None


class VerificationJudge(Protocol):
    def assess(self, check: VerificationSpec, raw: CommandResult, passed: bool, detail: str) -> tuple[str | None, str | None]: ...


class HeuristicVerificationJudge:
    name = "heuristic"

    def assess(self, check: VerificationSpec, raw: CommandResult, passed: bool, detail: str) -> tuple[str | None, str | None]:
        verdict = "pass" if passed else "fail"
        rationale = f"Heuristic verifier observed {detail}."
        return rationale, verdict


class LLMVerificationJudge:
    name = "llm"

    def __init__(self, config: LLMConfig, fallback: HeuristicVerificationJudge | None = None):
        self.client = OpenAICompatibleLLM(config)
        self.fallback = fallback or HeuristicVerificationJudge()

    def assess(self, check: VerificationSpec, raw: CommandResult, passed: bool, detail: str) -> tuple[str | None, str | None]:
        system_prompt = (
            "You are a safe Ops verification agent. Explain whether the check passed and summarize the operational meaning of the result. "
            "Return strict JSON with keys: rationale and verdict, where verdict is pass, fail, or uncertain."
        )
        user_payload = {
            "check": {
                "name": check.name,
                "command": check.command,
                "expect_exit_code": check.expect_exit_code,
                "expect_stdout_contains": check.expect_stdout_contains,
            },
            "observed": {
                "returncode": raw.returncode,
                "stdout": raw.stdout,
                "stderr": raw.stderr,
                "passed": passed,
                "detail": detail,
            },
        }
        try:
            result = self.client.complete_json(system_prompt, user_payload)
            return result.get("rationale"), result.get("verdict")
        except Exception:
            return self.fallback.assess(check, raw, passed, detail)


def build_verification_judge(
    verifier: str = "heuristic",
    model: str = "gpt-5.4",
    base_url: str = "https://api.openai.com/v1",
    api_key_env: str = "OPENAI_API_KEY",
) -> HeuristicVerificationJudge | LLMVerificationJudge:
    if verifier == "llm":
        return LLMVerificationJudge(LLMConfig(model=model, base_url=base_url, api_key_env=api_key_env))
    return HeuristicVerificationJudge()


class SkillVerifier:
    def __init__(self, runner: RemoteK8sRunner, judge: VerificationJudge | None = None):
        self.runner = runner
        self.judge = judge or HeuristicVerificationJudge()

    def verify(self, checks: list[VerificationSpec]) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for check in checks:
            raw = self.runner.run(check.command, check=False)
            passed = raw.returncode == check.expect_exit_code
            detail = f"exit={raw.returncode}"
            if passed and check.expect_stdout_contains:
                passed = check.expect_stdout_contains in raw.stdout
                detail = f"stdout contains '{check.expect_stdout_contains}'"
            if not passed and raw.stderr:
                detail = raw.stderr
            elif not passed and raw.stdout:
                detail = raw.stdout
            rationale, verdict = self.judge.assess(check, raw, passed, detail)
            results.append(
                VerificationResult(
                    name=check.name,
                    passed=passed,
                    detail=detail,
                    raw=raw,
                    agent_rationale=rationale,
                    agent_verdict=verdict,
                )
            )
        return results
