from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .agent import ManagerAgent
from .generator import write_skill
from .optimizer import build_optimizer
from .reporting import load_report, save_report
from .remote import CommandResult
from .skill_schema import ClusterConfig, SkillSpec
from .verifier import VerificationResult
from .workflow import ExecutionReport, SkillExecutor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpsSkill minimal framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a skill spec")
    validate_parser.add_argument("skill", help="Path to skill YAML")

    generate_parser = subparsers.add_parser("generate", help="Generate a skill from a task card")
    generate_parser.add_argument("task_card", help="Path to task card YAML")
    generate_parser.add_argument("output", help="Path to output skill YAML")
    generate_parser.add_argument("--generator", choices=["template", "llm"], default="template")
    generate_parser.add_argument("--model", default="gpt-5.4")
    generate_parser.add_argument("--base-url", default="https://api.openai.com/v1")
    generate_parser.add_argument("--api-key-env", default="OPENAI_API_KEY")

    run_parser = subparsers.add_parser("run", help="Run or dry-run a skill")
    run_parser.add_argument("skill", help="Path to skill YAML")
    run_parser.add_argument("cluster", help="Path to cluster config YAML")
    run_parser.add_argument("--execute", action="store_true", help="Execute actions instead of verification-only")
    run_parser.add_argument("--report-out", help="Optional path to save the execution report as JSON")
    run_parser.add_argument("--verifier", choices=["heuristic", "llm"], default="heuristic")
    run_parser.add_argument("--verifier-model", default="gpt-5.4")
    run_parser.add_argument("--verifier-base-url", default="https://api.openai.com/v1")
    run_parser.add_argument("--verifier-api-key-env", default="OPENAI_API_KEY")

    rollback_parser = subparsers.add_parser("rollback", help="Run rollback actions")
    rollback_parser.add_argument("skill", help="Path to skill YAML")
    rollback_parser.add_argument("cluster", help="Path to cluster config YAML")

    review_parser = subparsers.add_parser("review", help="Review a saved execution report")
    review_parser.add_argument("report", help="Path to execution report JSON")
    review_parser.add_argument("--optimizer", choices=["heuristic", "llm"], default="heuristic")
    review_parser.add_argument("--optimizer-model", default="gpt-5.4")
    review_parser.add_argument("--optimizer-base-url", default="https://api.openai.com/v1")
    review_parser.add_argument("--optimizer-api-key-env", default="OPENAI_API_KEY")

    agent_parser = subparsers.add_parser("agent", help="Run the manager agent across staged skills")
    agent_parser.add_argument("cluster", help="Path to cluster config YAML")
    agent_parser.add_argument("--task-card", help="Optional path to a task card YAML used for skill selection")
    agent_parser.add_argument("--skills-root", default="skills", help="Root folder containing skill YAML files")
    agent_parser.add_argument(
        "--stages",
        nargs="+",
        default=["detection", "diagnosis", "recovery"],
        help="Stages the agent is allowed to run",
    )
    agent_parser.add_argument(
        "--max-skills-per-stage",
        type=int,
        default=1,
        help="Maximum number of skills the agent selects per stage",
    )
    agent_parser.add_argument(
        "--allow-mutation",
        action="store_true",
        help="Allow the agent to execute mutating recovery skills",
    )
    agent_parser.add_argument(
        "--planner",
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Planner backend used for skill selection",
    )
    agent_parser.add_argument(
        "--planner-model",
        default="gpt-5.4",
        help="Model name for the LLM planner when --planner llm is used",
    )
    agent_parser.add_argument(
        "--planner-base-url",
        default="https://api.openai.com/v1",
        help="OpenAI-compatible base URL for the LLM planner",
    )
    agent_parser.add_argument(
        "--planner-api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the API key for the LLM planner",
    )
    agent_parser.add_argument(
        "--verifier",
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Verification backend used for check interpretation",
    )
    agent_parser.add_argument("--verifier-model", default="gpt-5.4")
    agent_parser.add_argument("--verifier-base-url", default="https://api.openai.com/v1")
    agent_parser.add_argument("--verifier-api-key-env", default="OPENAI_API_KEY")
    agent_parser.add_argument(
        "--report-out",
        help="Optional path to save the agent execution report as JSON",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate":
        skill = SkillSpec.from_file(args.skill)
        print(json.dumps(asdict(skill), indent=2, ensure_ascii=False))
        return

    if args.command == "generate":
        skill = write_skill(
            args.task_card,
            args.output,
            generator=args.generator,
            model=args.model,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
        )
        print(f"Generated skill: {skill.name}")
        return

    if args.command == "review":
        raw_report = load_report(args.report)
        report = _report_from_dict(raw_report)
        optimizer = build_optimizer(
            args.optimizer,
            model=args.optimizer_model,
            base_url=args.optimizer_base_url,
            api_key_env=args.optimizer_api_key_env,
        )
        output = {
            "skill_name": report.skill_name,
            "succeeded": report.succeeded,
            "score": report.score,
            "optimizer_requested": args.optimizer,
            "suggestions": optimizer.suggest(report),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    if args.command == "agent":
        cluster = ClusterConfig.from_file(args.cluster)
        agent = ManagerAgent(
            cluster,
            skills_root=args.skills_root,
            planner=args.planner,
            planner_model=args.planner_model,
            planner_base_url=args.planner_base_url,
            planner_api_key_env=args.planner_api_key_env,
            verifier=args.verifier,
            verifier_model=args.verifier_model,
            verifier_base_url=args.verifier_base_url,
            verifier_api_key_env=args.verifier_api_key_env,
        )
        report = agent.run(
            task_card_path=args.task_card,
            stages=args.stages,
            max_skills_per_stage=args.max_skills_per_stage,
            allow_mutation=args.allow_mutation,
            execute_actions=True,
        )
        if args.report_out:
            save_report(report, args.report_out)
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
        if not report.succeeded:
            raise SystemExit(1)
        return

    skill = SkillSpec.from_file(args.skill)
    cluster = ClusterConfig.from_file(args.cluster)
    executor = SkillExecutor(
        cluster,
        verifier=args.verifier,
        verifier_model=args.verifier_model,
        verifier_base_url=args.verifier_base_url,
        verifier_api_key_env=args.verifier_api_key_env,
    )

    if args.command == "rollback":
        results = executor.rollback(skill)
        print(json.dumps([asdict(item) for item in results], indent=2, ensure_ascii=False))
        return

    report = executor.run(skill, execute_actions=args.execute)
    if args.report_out:
        save_report(report, args.report_out)
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    if not report.succeeded:
        raise SystemExit(1)


def _report_from_dict(payload: dict) -> ExecutionReport:
    return ExecutionReport(
        skill_name=payload["skill_name"],
        preconditions=[_verification_result_from_dict(item) for item in payload.get("preconditions", [])],
        actions=[_command_result_from_dict(item) for item in payload.get("actions", [])],
        success_criteria=[_verification_result_from_dict(item) for item in payload.get("success_criteria", [])],
        rollback=[_command_result_from_dict(item) for item in payload.get("rollback", [])],
    )


def _verification_result_from_dict(payload: dict) -> VerificationResult:
    return VerificationResult(
        name=payload["name"],
        passed=payload["passed"],
        detail=payload["detail"],
        raw=_command_result_from_dict(payload["raw"]),
        agent_rationale=payload.get("agent_rationale"),
        agent_verdict=payload.get("agent_verdict"),
    )


def _command_result_from_dict(payload: dict) -> CommandResult:
    return CommandResult(
        command=payload["command"],
        returncode=payload["returncode"],
        stdout=payload.get("stdout", ""),
        stderr=payload.get("stderr", ""),
    )


if __name__ == "__main__":
    main()

