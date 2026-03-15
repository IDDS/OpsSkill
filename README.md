# OpsSkill

OpsSkill is a minimal framework for autonomous Ops skill generation, validation, and optimization against a remote Kubernetes cluster.

## What is included

- `opsskill/generator.py`: generate a draft skill from a task card.
- `opsskill/skill_schema.py`: typed schema loader and validation.
- `opsskill/remote.py`: remote runner over SSH + jump host.
- `opsskill/verifier.py`: verification checks for preconditions and success criteria.
- `opsskill/workflow.py`: execution, rollback, and reporting.
- `opsskill/agent.py`: manager agent for staged skill selection and orchestration.
- `opsskill/llm.py`: shared OpenAI-compatible client for LLM-assisted generation, verification, optimization, and planning.
- `skills/check_namespace_access.yaml`: zero-risk connectivity and RBAC smoke test.
- `skills/restart_deployment.yaml`: example Kubernetes recovery skill.
- `configs/cluster.example.yaml`: remote cluster access config.

## Quick start

```bash
cd OpsSkill
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m opsskill.cli validate skills/restart_deployment.yaml
python -m opsskill.cli generate examples/task_card.yaml skills/generated_recover.yaml
python -m opsskill.cli generate examples/task_card.yaml skills/generated_llm.yaml --generator llm --model gpt-5.4
python -m opsskill.cli run skills/check_namespace_access.yaml configs/cluster.example.yaml --execute
python -m opsskill.cli run skills/check_namespace_access.yaml configs/cluster.example.yaml --execute --verifier llm --verifier-model gpt-5.4
python -m opsskill.cli run skills/check_namespace_access.yaml configs/cluster.example.yaml --execute --report-out results/check_namespace_access.json
python -m opsskill.cli review results/check_namespace_access.json --optimizer llm --optimizer-model gpt-5.4
python -m opsskill.cli agent configs/cluster.opsskill_exp.yaml --task-card examples/task_card.yaml --stages detection diagnosis --max-skills-per-stage 1 --report-out results/agent_readonly.json
python -m opsskill.cli agent configs/cluster.opsskill_exp.yaml --task-card examples/task_card.yaml --planner llm --planner-model gpt-5.4 --planner-base-url https://api.openai.com/v1 --report-out results/agent_llm.json
python -m opsskill.cli run skills/restart_deployment.yaml configs/cluster.example.yaml
python -m opsskill.cli run skills/restart_deployment.yaml configs/cluster.example.yaml --execute
bash scripts/run_pilot_faults.sh fast
bash scripts/run_pilot_faults.sh paper
```

## Design notes

A skill is defined as:

- `preconditions`: checks that must pass before actions run.
- `actions`: remote commands to execute through SSH.
- `success_criteria`: checks used to decide whether the skill worked.
- `rollback`: compensating commands if execution fails.

The manager agent uses a safe default policy:

- read-only detection and diagnosis skills can run by default
- mutating recovery skills require `--allow-mutation`
- `--planner heuristic` uses a deterministic task-card-driven selector
- `--planner llm` uses an OpenAI-compatible planner backend and falls back to heuristic selection if the API is unavailable
- the default LLM planner model name is `gpt-5.4`

LLM or agent participation is available in all four key stages:

- **skill generation**: `generate --generator llm`
- **skill verification**: `run --verifier llm`
- **skill optimization**: `review --optimizer llm`
- **skill orchestration**: `agent --planner llm`

Each LLM-assisted stage automatically falls back to a deterministic backend if the API is unavailable.

Pilot fault injection supports two modes:

- `fast`: shorter chaos duration and observation window for local debugging
- `paper`: longer, fixed observation window for reproducible paper-quality experiments

## Suggested next steps

1. Add Prometheus-based success criteria.
2. Add a trajectory store for failed attempts and reflections.
3. Add a policy engine to block risky cluster-scoped actions.
4. Add benchmark tasks with hidden validation checks.

## Research docs

- `docs/research_agenda.md`: research gaps, innovation points, and hypotheses.
- `docs/experiment_plan.md`: task families, baselines, metrics, and ablations.
- `docs/paper_outline.md`: paper structure and contribution framing.
- `docs/related_work_notes.md`: concise related-work positioning notes.
- `docs/acm_ieee_related_work.md`: ACM/IEEE-focused paper list and citation guidance.
- `docs/related_work_zh_draft.md`: Chinese related-work draft.
- `docs/citation_checklist.md`: must-cite references for the first paper.
- `docs/introduction_zh_draft.md`: Chinese introduction draft.
- `docs/problem_formulation_zh_draft.md`: Chinese problem formulation draft.
- `docs/method_zh_draft.md`: Chinese method draft.
- `docs/abstract_zh_draft.md`: Chinese abstract draft.
- `docs/contribution_zh.md`: contribution statement draft.
- `docs/task_benchmark_design.md`: benchmark design notes.
- `docs/paper_writing_plan.md`: week-by-week writing plan.
- `docs/ops_workflow_skill_catalog_zh.md`: detection-RCA-recovery skill catalog.
- `docs/skill_stage_mapping_zh.md`: workflow-to-skill stage mapping notes.
- `docs/experiment_ready_skills.md`: experiment-ready metadata format for skill cards.
- `docs/method_innovation_summary_zh.md`: concise method novelty and theory summary.
- `docs/agent_planner_zh.md`: manager agent and planner design notes.
- `examples/initial_skill_catalog.yaml`: structured initial skill catalog.
- `examples/benchmark_task_instances.yaml`: benchmark-oriented task instance examples.
