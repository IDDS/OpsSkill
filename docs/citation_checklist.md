# Citation Checklist for the First OpsSkill Paper

## Must-cite core papers
- DeCaf: diagnosing and triaging performance issues in large-scale cloud services
- Mining root cause knowledge from cloud service incident investigations for AIOps
- AutoTSG: learning and synthesis for incident troubleshooting
- Actionable and interpretable fault localization for recurring failures in online service systems
- AI-Governance and Levels of Automation for AIOps-supported System Administration

## Strong supporting citations
- Neural Knowledge Extraction From Cloud Service Incidents
- MicroDiag: Fine-grained Performance Diagnosis for Microservice Systems
- Diagnosing Performance Issues for Large-Scale Microservice Systems With Heterogeneous Graph
- ReconRCA: Root Cause Analysis in Microservices with Incomplete Metrics
- Human-in-the-Loop Runbook Improvement with Agentic Support Automation
- Tool Playgrounds: A Comprehensive and Analyzable Benchmark for LLM Tool Invocation

## Optional but highly relevant
- Nissist: An Incident Mitigation Copilot based on Troubleshooting Guides
- Generative AI for Software Engineering: Survey and Open Problems

## Section mapping
- Introduction: DeCaf, Mining root cause knowledge..., AI-Governance..., Generative AI for Software Engineering...
- Related work: AutoTSG, Actionable and interpretable fault localization..., Neural Knowledge Extraction..., MicroDiag, Nissist
- Benchmark: Tool Playgrounds, ReconRCA
- Safety and discussion: AI-Governance..., Human-in-the-Loop Runbook Improvement..., Nissist

## Practical advice
- Prefer citing system papers that show real operational workflow, not only abstract AIOps surveys.
- Use at least one citation for each of these claims:
  - operational incidents can be mined into reusable knowledge
  - diagnosis alone is insufficient for end-to-end automation
  - runbooks/troubleshooting guides are a useful prior for automation
  - safe autonomy requires governance or human oversight
  - existing evaluation does not cover real remote Kubernetes skill execution
