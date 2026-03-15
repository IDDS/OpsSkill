# OpsSkill Research Agenda

## 1. Research Problem

OpsSkill studies how to automatically generate, validate, and optimize reusable operations skills for real-world cloud-native systems. Compared with generic LLM agents, the key challenge is not only producing tool calls, but compiling an operational task into a safe, verifiable, and reusable skill that can execute on a remote Kubernetes cluster.

We define an Ops skill as a typed, executable artifact with five components:

1. Preconditions: environment and capability checks before execution.
2. Actions: ordered tool calls or commands.
3. Success criteria: multi-signal verification rules.
4. Rollback plan: compensating operations when a mutation fails.
5. Risk label: blast-radius and safety metadata.

## 2. Main Research Gaps

### Gap 1: Missing typed skill representation for Ops
Existing agents mostly emit free-form command sequences or ReAct traces. They do not explicitly model preconditions, rollback, or hidden verification.

**Innovation I1**: Propose a Typed Ops Skill IR that compiles a task card into a structured skill with preconditions, actions, success criteria, rollback, and risk labels.

**Hypothesis H1**: Typed Skill IR improves structural validity, first-pass success rate, and rollback coverage over direct command generation.

### Gap 2: Missing hidden verification on real remote Kubernetes environments
Most works validate agent behavior through visible tool outputs or simulated environments. In Ops, a command may appear successful while the service is still unhealthy.

**Innovation I2**: Design a remote-K8s hidden verifier that combines object state, rollout status, logs, events, and optional SLO metrics to determine whether a task is truly solved.

**Hypothesis H2**: Hidden verification reveals a large false-positive gap in baseline agents and reduces overestimation of success.

### Gap 3: Missing policy-gated execution for autonomous Ops skills
Generic agent frameworks optimize for task completion, but they do not explicitly minimize blast radius in real systems.

**Innovation I3**: Introduce a policy-gated execution loop with capability probes, risk budgets, canary namespaces, and rollback triggers.

**Hypothesis H3**: Policy gating significantly reduces unsafe actions and rollback frequency with only minor impact on task completion.

### Gap 4: Missing structured failure-driven optimization
Reflection-based methods rely on free-text memory. In Ops, failure often has recurring structure such as RBAC denial, resource not found, rollout timeout, or readiness failure.

**Innovation I4**: Learn from structured failure signatures extracted from execution reports instead of only free-text reflections.

**Hypothesis H4**: Structured failure memory improves sample efficiency and stability compared with plain textual reflection.

### Gap 5: Missing cross-cluster portability
A skill that works on one cluster may fail on another because of version, RBAC, CRD, or namespace differences.

**Innovation I5**: Model a cluster capability graph and use it to adapt skills across environments.

**Hypothesis H5**: Capability-aware adaptation improves zero-shot and few-shot transfer to new clusters.

## 3. Recommended Paper Positioning

### Option A: Systems paper
**Title direction**: Policy-Gated Autonomous Ops Skill Learning and Validation on Remote Kubernetes

Best when emphasizing:
- end-to-end architecture
- safe execution
- hidden verification
- online optimization

### Option B: Benchmark paper
**Title direction**: OpsSkill-Bench: A Benchmark for Autonomous Operations Skill Learning on Remote Kubernetes

Best when emphasizing:
- task card dataset
- hidden verifier
- safety metrics
- standardized baselines

### Option C: Agent/learning paper
**Title direction**: Failure-Driven Skill Optimization for Safe Kubernetes Operations Agents

Best when emphasizing:
- structured failure memory
- skill optimization algorithm
- transfer across clusters

## 4. Strongest Publishable Narrative

The strongest narrative is not "LLM for AIOps", but:

> We present the first framework for compiling operational tasks into safe, verifiable, and optimizable skills that run on real remote Kubernetes clusters under explicit safety constraints.

This statement is stronger because it highlights:
- typed skill representation
- remote real-environment validation
- safety and rollback
- iterative optimization

## 5. Concrete Research Questions

- RQ1: Can typed skill compilation outperform direct command generation for Kubernetes troubleshooting tasks?
- RQ2: How much do visible-only evaluators overestimate agent success compared with hidden multi-signal verification?
- RQ3: Can policy-gated execution reduce unsafe actions without significantly hurting task completion?
- RQ4: Does structured failure memory improve skill optimization more effectively than free-text reflection?
- RQ5: How well do learned Ops skills transfer across clusters with different capabilities?

## 6. Suggested Initial Scope

For a first paper, prioritize I1 + I2 + I3 as the core system contribution. Treat I4 and I5 as optional extensions or ablation modules.

This gives a publishable minimal story:
- typed skill compilation
- remote hidden verification
- policy-gated execution
- experiments on real Kubernetes tasks
