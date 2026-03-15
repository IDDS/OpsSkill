# OpsSkill Task Benchmark Design

## Goal

Build a benchmark that evaluates autonomous Ops skill generation and execution on remote Kubernetes rather than simulated tools.

## Task Instance Format

Each task instance should include:
- task description
- target namespace
- allowed scope
- available tools
- hidden success condition
- safety constraints
- optional rollback expectation

## Fault Categories

- workload crash or restart anomaly
- configuration mismatch
- service routing issue
- resource scaling issue
- RBAC denial or capability mismatch
- missing dependency or unavailable CRD

## Instance Construction Strategy

### Manual seed tasks
Start from real troubleshooting patterns and convert them into task cards.

### Programmatic fault injection
Create reproducible fault states via scripted changes in namespace sandboxes.

### Hidden validation
Keep some checks separate from the skill specification so agents cannot overfit to visible criteria.

## Evaluation Labels

For each run, store:
- visible success
- hidden success
- unsafe action attempted
- rollback triggered
- rollback succeeded
- latency
- cost

## Benchmark Value

This benchmark is publishable because most existing agent benchmarks do not combine:
- real remote infrastructure
- hidden end-state validation
- safety-aware scoring
- rollback assessment
