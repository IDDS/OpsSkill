# Related Work Notes for OpsSkill

## Tool-use and Skill Learning

- ReAct: strong interaction pattern, weak safety semantics for Ops.
- Toolformer: strong tool selection, weak multi-step operational control.
- Reflexion: strong textual feedback loop, weak structured failure modeling.
- Voyager: strong skill accumulation idea, but not designed for real infrastructure.
- Gorilla: strong API grounding, weak end-state operational verification.

## Evaluation and Benchmarks

- AgentBench: broad interaction benchmark, not Ops-specific.
- SWE-agent / SWE-bench: realistic environment and hidden validation ideas, but code-centric instead of infra-centric.
- tau-bench: strong hidden state evaluation, but not Kubernetes.
- ToolSandbox: good stateful tool testing, but mostly simulated.

## Ops and Kubernetes Systems

- K8sGPT: useful diagnosis baseline, limited autonomous skill execution and optimization.
- BotKube: good ChatOps integration, not autonomous skill learning.
- Kyverno / OPA Gatekeeper: strong safety controls, but not learning systems.

## Writing Guidance

When writing the related work section, avoid saying simply that prior work does not target DevOps. Instead, say more precisely:
- they do not compile tasks into typed, reusable skills
- they do not verify success through hidden multi-signal evaluation on remote clusters
- they do not optimize from structured execution reports under safety constraints
