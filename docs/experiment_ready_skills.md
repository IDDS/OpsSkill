# Experiment-Ready Skill Format

This document defines how the paper-oriented skill cards extend the base OpsSkill schema without breaking runtime compatibility.

## Principle

The current runtime consumes these top-level fields:
- `version`
- `name`
- `intent`
- `namespace`
- `preconditions`
- `actions`
- `success_criteria`
- `rollback`
- `metadata`

To keep compatibility, all experiment-only annotations are stored under `metadata`.

## Experiment metadata fields

### `metadata.benchmark`
Used to group skills into benchmark families and paper analyses.

Recommended fields:
- `included_in`: benchmark version such as `opsskill-paper-v1`
- `task_family`: family name used in tables and plots
- `mutability`: `read-only` or `mutating`
- `evaluation_focus`: key metrics emphasized for this skill
- `benchmark_tags`: short tags for filtering and grouping

### `metadata.instance_parameters`
Defines how a skill should be instantiated for a concrete task instance.

Typical fields:
- namespace or namespace environment variable
- deployment / pod / service name
- placeholder values that must be specialized before execution
- expected failure modes

### `metadata.hidden_checks`
Stores hidden-verification hints used by benchmark code or manual evaluation.
Each hidden check may include:
- `name`
- `signal`
- `command`

These checks are intentionally not part of `success_criteria`, because they are meant to evaluate the skill rather than guide it directly.

## Design guidance by stage

### Detection skills
- usually `read-only`
- hidden checks should focus on evidence completeness and signal visibility
- instance parameters should mainly capture namespace, query scope, and target signals

### Diagnosis skills
- usually `read-only`
- hidden checks should focus on evidence grounding and candidate quality
- instance parameters should capture target kinds, expected failure patterns, and candidate sets

### Recovery skills
- usually `mutating`
- hidden checks should focus on real recovery quality beyond visible rollout success
- instance parameters should capture target object names, rollback targets, and template placeholders

## Recommended paper usage

In the paper, these metadata fields support:
- benchmark task grouping
- hidden success evaluation
- ablation analysis by stage or mutability
- transfer studies through explicit parameter specialization
