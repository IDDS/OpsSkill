# ACM / IEEE Related Work Notes for OpsSkill

本文档聚焦可从 ACM Digital Library 与 IEEE Xplore 获取、且与 OpsSkill 最相关的论文，用于引言与相关工作撰写。

## 1. Incident Knowledge and AIOps

### DeCaf: diagnosing and triaging performance issues in large-scale cloud services
- Venue: ICSE-SEIP 2020
- URL: https://dl.acm.org/doi/10.1145/3377813.3381353
- Relevance:
  - Shows that cloud incident handling is a pipeline of diagnosis and triage rather than a single prediction task.
  - Supports the claim that Ops work should be decomposed into reusable sub-skills.
- How to cite:
  - Use in the introduction to motivate that real incident handling is multi-stage and operationally grounded.

### AI-Governance and Levels of Automation for AIOps-supported System Administration
- Venue: ICCCN 2020
- URL: https://ieeexplore.ieee.org/document/9209606/
- Relevance:
  - Provides a governance and automation-level perspective for AIOps-supported administration.
  - Strong citation for safety, human oversight, and controlled autonomy.
- How to cite:
  - Use in safety discussion and related work to justify policy-gated execution instead of unconstrained autonomy.

### Neural Knowledge Extraction From Cloud Service Incidents
- Venue: ICSE-SEIP 2021
- URL: https://ieeexplore.ieee.org/document/9402085/
- Relevance:
  - Demonstrates that cloud incident records can be converted into structured knowledge.
  - Strong support for learning skills from incident investigations and runbooks.
- How to cite:
  - Use when arguing that operational data can be transformed into reusable skills or skill priors.

### Mining root cause knowledge from cloud service incident investigations for AIOps
- Venue: ICSE-SEIP 2022
- URL: https://dl.acm.org/doi/10.1145/3510457.3513030
- Relevance:
  - One of the strongest prior works for converting incident investigations into reusable root-cause knowledge.
  - Closest precursor to learning from historical operations traces, though it stops short of executable skill learning.
- How to cite:
  - Use as a key bridge paper between AIOps knowledge mining and OpsSkill’s executable skill representation.

## 2. Diagnosis and Root Cause Analysis

### MicroDiag: Fine-grained Performance Diagnosis for Microservice Systems
- Venue: IEEE/ACM CloudIntelligence Workshop 2021
- URL: https://ieeexplore.ieee.org/document/9527007/
- Relevance:
  - Focuses on fine-grained diagnosis in microservice systems.
  - Supports the need for intermediate diagnostic skill steps before repair actions.
- How to cite:
  - Use in related work on microservice diagnosis and the limits of diagnosis-only systems.

### Actionable and interpretable fault localization for recurring failures in online service systems
- Venue: ESEC/FSE 2022
- URL: https://dl.acm.org/doi/10.1145/3540250.3549092
- Relevance:
  - Emphasizes actionable and interpretable localization rather than black-box prediction.
  - Aligns well with OpsSkill’s auditable and reusable skill abstraction.
- How to cite:
  - Use to motivate that actionable intelligence is more useful than plain fault ranking.

### Diagnosing Performance Issues for Large-Scale Microservice Systems With Heterogeneous Graph
- Venue: IEEE Transactions on Services Computing 2024
- URL: https://ieeexplore.ieee.org/document/10533869/
- Relevance:
  - Represents a strong recent diagnosis baseline for cloud-native systems.
  - Helps position OpsSkill as broader than diagnosis: it includes execution, verification, rollback, and optimization.
- How to cite:
  - Use as a high-quality diagnosis baseline in related work.

### ReconRCA: Root Cause Analysis in Microservices with Incomplete Metrics
- Venue: ICWS 2025
- URL: https://ieeexplore.ieee.org/document/11169641/
- Relevance:
  - Important because real Ops settings often have incomplete or noisy telemetry.
  - Supports the need for multi-signal verification and capability-aware execution.
- How to cite:
  - Use to justify why the benchmark should not assume perfect observability.

## 3. Troubleshooting Guides, Runbooks, and Incident Copilots

### AutoTSG: learning and synthesis for incident troubleshooting
- Venue: ESEC/FSE 2022
- URL: https://dl.acm.org/doi/10.1145/3540250.3558958
- Relevance:
  - One of the most directly relevant papers to OpsSkill.
  - Connects troubleshooting-guide knowledge with automated synthesis, but does not fully address safe remote execution or hidden verification.
- How to cite:
  - Use as the nearest related work for runbook-to-skill transformation.

### Human-in-the-Loop Runbook Improvement with Agentic Support Automation
- Venue: CogMI 2025
- URL: https://ieeexplore.ieee.org/document/11417021/
- Relevance:
  - Strong citation for human oversight in runbook automation.
  - Supports a staged autonomy narrative rather than fully unconstrained agents.
- How to cite:
  - Use in safety and system design sections to justify gated execution and review loops.

## 4. Benchmark and Evaluation Motivation

### Tool Playgrounds: A Comprehensive and Analyzable Benchmark for LLM Tool Invocation
- Venue: ICASSP 2025
- URL: https://ieeexplore.ieee.org/document/10890828/
- Relevance:
  - Good benchmark citation for general tool-use evaluation.
  - Useful mainly because it highlights what existing benchmarks still miss for Ops: real clusters, safety constraints, and rollback-aware scoring.
- How to cite:
  - Use to contrast generic tool-use evaluation with a remote-Kubernetes benchmark.

### Generative AI for Software Engineering: Survey and Open Problems
- Venue: ICSE-FoSE 2023
- URL: https://ieeexplore.ieee.org/document/10449667/
- Relevance:
  - Broadly useful for framing trustworthiness, evaluation, and controllability concerns of generative systems.
  - Not Ops-specific, but strong for positioning the problem.
- How to cite:
  - Use in the introduction to situate OpsSkill within the broader GenAI-for-SE trend.

## 5. Optional Non-ACM/IEEE But Highly Relevant Citation

### Nissist: An Incident Mitigation Copilot based on Troubleshooting Guides
- Venue: ECAI 2024
- URL: https://ebooks.iospress.nl/doi/10.3233/FAIA241032
- Relevance:
  - Very close in spirit to OpsSkill because it uses troubleshooting guides for incident mitigation.
  - Worth citing even though it is outside ACM/IEEE.
- How to cite:
  - Use as a direct neighboring work on guide-driven incident copilots.

## 6. Strongest Citation Bundle by Section

### Introduction
- DeCaf
- Mining root cause knowledge from cloud service incident investigations for AIOps
- AI-Governance and Levels of Automation for AIOps-supported System Administration
- Generative AI for Software Engineering: Survey and Open Problems

### Related Work
- AutoTSG
- Actionable and interpretable fault localization for recurring failures in online service systems
- Diagnosing Performance Issues for Large-Scale Microservice Systems With Heterogeneous Graph
- Neural Knowledge Extraction From Cloud Service Incidents
- MicroDiag
- Nissist

### Benchmark Motivation
- Tool Playgrounds
- ReconRCA
- Actionable and interpretable fault localization for recurring failures in online service systems

### Safety Motivation
- AI-Governance and Levels of Automation for AIOps-supported System Administration
- Human-in-the-Loop Runbook Improvement with Agentic Support Automation
- Nissist

## 7. Recommended Related-Work Narrative

A clean related-work section can be organized into four paragraphs:

1. **AIOps and incident knowledge mining**
   - DeCaf, Neural Knowledge Extraction..., Mining root cause knowledge...
   - Claim: prior work extracts knowledge from incidents, but stops short of compiling safe executable skills.

2. **Microservice diagnosis and fault localization**
   - MicroDiag, Actionable and interpretable fault localization..., Diagnosing Performance Issues..., ReconRCA
   - Claim: prior work improves diagnosis quality, but typically handles one subtask rather than end-to-end troubleshooting.

3. **Runbooks, troubleshooting guides, and copilots**
   - AutoTSG, Human-in-the-Loop Runbook Improvement..., Nissist
   - Claim: these works approach the problem most closely, but lack a unified typed skill representation, hidden verification, and safety-aware benchmark.

4. **Evaluation and safety**
   - Tool Playgrounds, AI-Governance..., Generative AI for Software Engineering...
   - Claim: existing benchmarks evaluate generic tool use or discuss automation levels, but not remote-Kubernetes operations skills with rollback and blast-radius metrics.

## 8. One-Sentence Positioning

OpsSkill should be positioned not as another generic AIOps copilot, but as a framework for learning safe, verifiable, and optimizable operations skills that execute on real remote Kubernetes environments.
