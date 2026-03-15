# OpsSkill Experiment Plan

## 1. Experimental Goal

Evaluate whether OpsSkill can generate safer, more reliable, and more reusable operations skills than generic LLM agent baselines on remote Kubernetes tasks.

## 2. Task Families

Construct at least four task families, each with 5-10 instances.

### T1. Read-only diagnosis tasks
Examples:
- identify CrashLoopBackOff root cause
- locate failing namespace or deployment
- determine whether a service endpoint is reachable

Purpose:
- evaluate tool use and diagnosis without mutation risk

### T2. Lightweight recovery tasks
Examples:
- rollout restart deployment
- scale replicas back to target value
- restart a stuck job or pod

Purpose:
- evaluate basic action correctness and hidden verification

### T3. Configuration repair tasks
Examples:
- fix wrong image tag
- restore missing environment variable
- patch a broken service selector

Purpose:
- evaluate multi-step actions and rollback logic

### T4. Policy- and RBAC-constrained tasks
Examples:
- task requires namespace-level adaptation
- task fails under insufficient RBAC
- task involves unavailable CRDs or plugins

Purpose:
- evaluate safety gates and portability

## 3. Baselines

### B1. Direct command generation
Prompt the LLM to directly generate kubectl commands from the task description.

### B2. ReAct-style agent
Allow the model to reason, call tools, and iterate with observations.

### B3. Reflexion-style agent
Add textual reflection memory after each failed attempt.

### B4. Template or runbook baseline
Use manually written troubleshooting templates or nearest-neighbor retrieval from a small skill bank.

### B5. OpsSkill full system
Typed skill IR + policy gate + hidden verifier + report-driven optimization.

## 4. Metrics

Let success rate be $SR$, hidden-verifier pass rate be $HV$, unsafe action rate be $U$, rollback rate be $R$, latency be $L$, and cost be $C$.

A compact overall score can be:

$$
Score = \alpha SR + \beta HV - \gamma U - \delta R - \epsilon L - \zeta C
$$

### Primary metrics
- Task success rate
- Hidden verification pass rate
- First-pass success rate
- Unsafe action rate
- Rollback trigger rate
- Pass@k or pass^k stability

### Secondary metrics
- Average tool calls
- Wall-clock completion time
- Token cost
- Cross-cluster transfer success
- Human intervention count

## 5. Ablation Studies

### A1. Remove typed skill IR
Compare OpsSkill with direct command generation.

### A2. Remove hidden verification
Evaluate performance when only visible command outputs are used.

### A3. Remove policy gate
Measure changes in unsafe actions and rollback frequency.

### A4. Replace structured failure memory with free-text reflection
Measure sample efficiency and stability.

### A5. Remove capability-aware adaptation
Test cross-cluster performance drop.

## 6. Safety Evaluation

Safety should be a first-class evaluation axis.

### Safety dimensions
- whether the action exceeds intended namespace scope
- whether destructive commands are attempted
- whether rollback exists and works
- whether the system halts under policy violation

### Suggested reporting
- number of blocked risky actions
- number of unsafe but initially successful actions
- number of irreversible failures
- rollback success rate

## 7. Remote Kubernetes Validation Protocol

### Environment design
- use one primary remote cluster for development
- create dedicated namespaces for each task instance
- optionally prepare a second cluster or altered namespace policy for transfer evaluation

### Validation loop
1. inject or prepare a faulted state
2. provide a task card to the system
3. generate a skill
4. dry-run policy and capability checks
5. execute allowed actions
6. run visible checks
7. run hidden checks
8. record report and optimize if needed

### Practical fault-injection profiles
- `fast` profile: 20s-30s fault duration with a short observation wait, used for development and debugging
- `paper` profile: 60s-90s fault duration with a longer observation wait, used for official experiments and reported results

Recommended usage:
- use `fast` while iterating on scripts, skills, and prompts
- use `paper` when collecting the final numbers for the manuscript

## 8. Statistical Practice

- run each task with at least 3 random seeds or prompt variants
- report mean and standard deviation where possible
- use paired comparisons across the same task instances
- explicitly separate visible success from hidden success

## 9. Minimal Publishable Experiment Package

If resources are limited, the minimum convincing package is:
- 20-30 Kubernetes tasks
- 3 strong baselines
- 3 main metrics: hidden success, unsafe action rate, rollback rate
- 3 ablations: no IR, no policy gate, no hidden verifier

This is enough for a solid systems-style first paper.
