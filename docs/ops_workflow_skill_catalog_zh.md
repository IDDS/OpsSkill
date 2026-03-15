# 智能运维全流程初始 Skill 目录（中文）

## 1. 整体视角

智能运维的典型闭环通常包括三个核心阶段：

1. **故障检测（Detection）**：从指标、日志、调用链、事件和配置变更中发现异常。
2. **根因定位（Diagnosis / RCA）**：从多源观测数据中缩小故障范围、定位关键组件和可能根因。
3. **故障恢复（Recovery / Remediation）**：执行受控修复动作，并验证服务是否真正恢复。

对于 OpsSkill 而言，每个阶段都不应仅被看作一个模型能力，而应被拆解为一组可复用、可组合的 skill。一个完整的自治运维系统可以将不同阶段 skill 连接成技能图：检测 skill 触发 RCA skill，RCA skill 输出候选根因与处置建议，再由恢复 skill 执行修复与回滚。

---

## 2. 相关工作来源

### 2.1 学术文献启发

- **故障检测 / incident triage**
  - DeCaf (ICSE-SEIP 2020)
  - AI-Governance and Levels of Automation for AIOps-supported System Administration (ICCCN 2020)
- **知识抽取 / 根因知识学习**
  - Neural Knowledge Extraction From Cloud Service Incidents (ICSE-SEIP 2021)
  - Mining root cause knowledge from cloud service incident investigations for AIOps (ICSE-SEIP 2022)
- **根因定位 / 微服务诊断**
  - MicroDiag (CloudIntelligence 2021)
  - Actionable and interpretable fault localization for recurring failures in online service systems (FSE 2022)
  - Diagnosing Performance Issues for Large-Scale Microservice Systems With Heterogeneous Graph (TSC 2024)
  - ReconRCA (ICWS 2025)
- **恢复 / runbook / troubleshooting guide 自动化**
  - AutoTSG (FSE 2022)
  - Human-in-the-Loop Runbook Improvement with Agentic Support Automation (CogMI 2025)
  - Nissist (ECAI 2024)

### 2.2 商业软件启发

- **检测**：Datadog, Dynatrace, New Relic, Splunk Observability, PagerDuty AIOps
- **定位**：Dynatrace Davis AI, Splunk ITSI, Elastic Observability, IBM Instana, Datadog Watchdog
- **恢复**：PagerDuty Runbook Automation, Shoreline, IBM Turbonomic, Harness, OpsRamp

### 2.3 开源软件启发

- **检测**：Prometheus, Alertmanager, Loki, Elasticsearch, Jaeger, OpenTelemetry, Kubernetes Events
- **定位**：K8sGPT, BotKube, PromQL, kubectl, Argo Rollouts analysis, kube-state-metrics
- **恢复**：Argo CD, Helm, FluxCD, Keptn, KEDA, LitmusChaos, Kubernetes 原生 rollout/patch/scale 操作

---

## 3. 阶段一：故障检测 Skill

这一阶段的目标是从多源信号中判断“是否发生了值得处理的异常”，并形成结构化告警或任务卡。

### D1. 指标异常检测 Skill
- **目标**：识别 CPU、内存、延迟、错误率、QPS 等指标中的显著异常。
- **输入**：Prometheus 指标、时间窗口、服务标识。
- **工具**：PromQL、Prometheus API、Grafana API。
- **输出**：异常指标列表、异常时间段、可疑服务。
- **安全关注点**：只读，风险低。
- **典型来源**：Datadog anomaly detection、Dynatrace、Prometheus rule-based alerting。

### D2. 日志异常聚类 Skill
- **目标**：发现错误日志突增、异常日志模板或新出现的错误模式。
- **输入**：Loki / Elasticsearch 日志流，时间窗口。
- **工具**：Loki query、ES query、日志模板抽取器。
- **输出**：异常日志模式、top error signatures、受影响 Pod/服务。
- **安全关注点**：可能涉及敏感日志脱敏。
- **典型来源**：Splunk、Elastic Observability、日志模式挖掘论文。

### D3. 调用链异常热点检测 Skill
- **目标**：从 trace 中识别高延迟 span、错误传播路径和瓶颈服务。
- **输入**：Jaeger / Tempo / OpenTelemetry traces。
- **工具**：trace query API、span aggregation。
- **输出**：异常调用路径、热点 span、候选服务列表。
- **安全关注点**：只读。
- **典型来源**：分布式追踪分析系统、商业 APM。

### D4. Kubernetes 事件突发检测 Skill
- **目标**：从 Kubernetes Events 中发现 pod 重启、调度失败、镜像拉取失败、探针失败等事件。
- **输入**：namespace、时间窗口、event stream。
- **工具**：`kubectl get events`、K8s API。
- **输出**：事件摘要、事件频度、异常资源对象。
- **安全关注点**：只读。
- **典型来源**：K8sGPT、BotKube、Kubernetes event-based monitoring。

### D5. 配置变更关联检测 Skill
- **目标**：分析异常是否与近期 GitOps/Helm/ConfigMap/Secret 变更有关。
- **输入**：Git commit、Helm release 历史、K8s 对象变更记录。
- **工具**：Argo CD API、Git log、Helm history、audit log。
- **输出**：疑似相关变更、变更时间线、变更责任对象。
- **安全关注点**：注意审计信息访问权限。
- **典型来源**：Shoreline、Harness、变更关联分析产品。

### D6. SLO 违约检测 Skill
- **目标**：从用户体验或 SLI 指标中判断是否发生服务级退化。
- **输入**：成功率、延迟分位数、可用性指标。
- **工具**：PromQL、SLO dashboards、error budget API。
- **输出**：违约服务、严重等级、是否应触发 incident。
- **安全关注点**：只读。
- **典型来源**：SRE 实践、New Relic、Datadog SLO。

### D7. 多源告警去重与聚合 Skill
- **目标**：对指标、日志、trace、事件的重复告警进行聚类，减少告警风暴。
- **输入**：多源告警流。
- **工具**：PagerDuty AIOps、Alertmanager、聚类算法。
- **输出**：聚合后的 incident、主告警对象、影响范围。
- **安全关注点**：避免错误合并导致漏报。
- **典型来源**：PagerDuty AIOps、Splunk ITSI。

### D8. 任务卡生成 Skill
- **目标**：将检测阶段输出编译为标准化 task card，供 RCA 与恢复阶段使用。
- **输入**：异常摘要、影响范围、环境上下文。
- **工具**：LLM summarizer、模板系统。
- **输出**：task card（问题描述、目标对象、约束、优先级、可用工具）。
- **安全关注点**：摘要不能丢失关键上下文。
- **典型来源**：incident copilot、ticket enrichment 系统。

---

## 4. 阶段二：根因定位 Skill

这一阶段的目标是从检测结果出发，缩小故障范围，识别根因候选，并生成带置信度的处置建议。

### R1. 影响面界定 Skill
- **目标**：判断故障影响哪些 namespace、服务、依赖链路和用户请求路径。
- **输入**：task card、trace、service graph、error logs。
- **工具**：service map、Jaeger、PromQL、K8s API。
- **输出**：受影响拓扑、优先处理对象。
- **安全关注点**：只读。
- **典型来源**：Dynatrace service flow、Instana topology。

### R2. Top-K 根因候选生成 Skill
- **目标**：从多源观测中生成若干根因候选，例如配置错误、资源不足、依赖服务失败、RBAC 问题、镜像问题。
- **输入**：指标、日志、trace、events、最近变更。
- **工具**：规则库、LLM、知识图谱或异构图模型。
- **输出**：根因候选列表及置信度。
- **安全关注点**：避免过度自信输出。
- **典型来源**：Davis AI、K8sGPT、RCA 学术文献。

### R3. Pod/Deployment 状态诊断 Skill
- **目标**：识别 CrashLoopBackOff、ImagePullBackOff、OOMKilled、Pending、Readiness failure 等状态原因。
- **输入**：Pod 状态、describe 输出、容器日志。
- **工具**：`kubectl describe/get/logs`。
- **输出**：对象级根因标签、建议动作。
- **安全关注点**：日志只读访问权限。
- **典型来源**：K8sGPT、runbook、Kubernetes troubleshooting 经验。

### R4. 资源瓶颈定位 Skill
- **目标**：判断故障是否由 CPU、内存、磁盘、网络或 HPA 参数配置导致。
- **输入**：资源指标、节点状态、容器 limit/request。
- **工具**：PromQL、metrics-server、kubectl top。
- **输出**：资源瓶颈对象、资源异常解释。
- **安全关注点**：只读。
- **典型来源**：微服务性能诊断论文、Turbonomic。

### R5. 变更根因关联 Skill
- **目标**：确认是否由最近配置、镜像、流量策略、网络策略变更导致异常。
- **输入**：变更日志、GitOps diff、Helm release、event timeline。
- **工具**：Argo CD diff、Git history、kubectl diff。
- **输出**：最可疑变更项及证据。
- **安全关注点**：只读审计。
- **典型来源**：incident investigation mining、商业变更关联分析。

### R6. RBAC / 权限失败定位 Skill
- **目标**：判断异常是否源于服务账号、RoleBinding、Secret 权限或 API 授权失败。
- **输入**：事件、API 错误、审计日志。
- **工具**：`kubectl auth can-i`、audit logs。
- **输出**：权限缺失点、最小修复建议。
- **安全关注点**：权限分析本身需受限。
- **典型来源**：Kubernetes 安全运维经验。

### R7. 网络与服务路由故障定位 Skill
- **目标**：分析 Service selector、Endpoint、Ingress、DNS、NetworkPolicy 或 service mesh 配置异常。
- **输入**：Service/Endpoint/Ingress 对象、探测结果、trace。
- **工具**：`kubectl get svc,endpoints,ingress`、curl、DNS query。
- **输出**：路由链路故障点。
- **安全关注点**：探测流量要受控。
- **典型来源**：runbook、云原生网络排障实践。

### R8. 故障证据摘要 Skill
- **目标**：将 RCA 结果整理为结构化证据包，供恢复阶段调用。
- **输入**：多项 RCA 结果。
- **工具**：LLM summarizer、模板系统。
- **输出**：root-cause card（候选根因、证据、置信度、推荐恢复动作）。
- **安全关注点**：不能丢失反例和不确定性。
- **典型来源**：Nissist、incident copilots。

---

## 5. 阶段三：故障恢复 Skill

这一阶段的目标是在安全约束下执行修复动作，并验证是否真正恢复服务。

### F1. Deployment 重启恢复 Skill
- **目标**：对短暂故障或配置已修复的 workload 触发 rollout restart。
- **输入**：目标 deployment、namespace。
- **工具**：`kubectl rollout restart/status/undo`。
- **输出**：新的 rollout 状态、恢复结果。
- **安全关注点**：需限制作用域并支持 rollback。
- **典型来源**：Kubernetes 原生恢复操作。

### F2. 副本数恢复 Skill
- **目标**：将异常扩缩容后的 workload 恢复到目标 replicas。
- **输入**：当前副本数、目标副本数、SLO 状态。
- **工具**：`kubectl scale`、HPA API。
- **输出**：缩放结果、容量恢复情况。
- **安全关注点**：避免容量抖动。
- **典型来源**：KEDA、HPA、商业 autoscaling。

### F3. 配置回滚 Skill
- **目标**：当异常由最近变更引发时，回滚 ConfigMap、Helm release、GitOps revision 或 Deployment revision。
- **输入**：变更证据、当前版本、上一稳定版本。
- **工具**：Helm rollback、Argo CD sync、`kubectl rollout undo`。
- **输出**：回滚结果、版本恢复记录。
- **安全关注点**：需要隐藏验证，防止“回滚成功但业务仍异常”。
- **典型来源**：GitOps、Shoreline、runbook automation。

### F4. Pod 删除重建 Skill
- **目标**：对卡死 Pod、异常 init 容器或单点失效实例进行受控删除与重建。
- **输入**：Pod 名称、所属控制器。
- **工具**：`kubectl delete pod`。
- **输出**：Pod 重建状态、readiness 恢复情况。
- **安全关注点**：禁止对无控制器裸 Pod 随意删除。
- **典型来源**：K8s 运维经验、runbook。

### F5. 镜像/配置修补 Skill
- **目标**：修复错误镜像 tag、缺失环境变量、错误 selector 或 probe 参数。
- **输入**：RCA 证据、目标 patch。
- **工具**：`kubectl patch`、Helm values update、GitOps PR。
- **输出**：配置修复结果。
- **安全关注点**：属于中高风险操作，需要 policy gate。
- **典型来源**：AutoTSG、运维 runbook、GitOps 实践。

### F6. 依赖服务重连/重配 Skill
- **目标**：在数据库、缓存、消息队列地址配置错误时修正依赖配置或重启连接方。
- **输入**：依赖错误证据、目标连接参数。
- **工具**：patch config、restart workload、service discovery query。
- **输出**：依赖恢复结果。
- **安全关注点**：避免扩大影响面。
- **典型来源**：incident mitigation copilot、生产 runbook。

### F7. 网络策略修复 Skill
- **目标**：修复 NetworkPolicy、Service、Ingress、Endpoint 等导致的访问失败问题。
- **输入**：网络 RCA 证据、目标对象。
- **工具**：`kubectl patch/apply`、ingress controller API。
- **输出**：流量恢复结果。
- **安全关注点**：高风险，需要 canary 或 dry-run。
- **典型来源**：云原生网络运维、商业 service networking 管控。

### F8. RBAC 最小修复 Skill
- **目标**：最小化修复服务账号所缺失的权限，而非直接授予宽泛权限。
- **输入**：权限失败证据、目标 API 动作。
- **工具**：Role/RoleBinding patch、`kubectl auth can-i` 验证。
- **输出**：权限修复结果。
- **安全关注点**：高风险，必须有最小权限约束。
- **典型来源**：安全运维、policy-aware remediation。

### F9. 恢复后隐藏验证 Skill
- **目标**：从用户请求成功率、事件流、readiness、trace 和 SLO 指标判断是否真正恢复。
- **输入**：恢复动作结果、多源观测。
- **工具**：PromQL、curl、kubectl、trace query。
- **输出**：恢复结论、隐藏成功率标签。
- **安全关注点**：只读。
- **典型来源**：OpsSkill 的核心创新方向。

### F10. 自动回滚 Skill
- **目标**：当恢复动作失败或效果不佳时触发补偿动作，恢复到最近稳定状态。
- **输入**：失败报告、回滚策略、最近稳定版本。
- **工具**：rollout undo、Helm rollback、Argo CD sync。
- **输出**：回滚结果、事故状态更新。
- **安全关注点**：回滚本身也需验证。
- **典型来源**：Shoreline、GitOps 回滚、Kubernetes 原生回退。

---

## 6. 推荐的初始 Skill 集合

如果要做一篇第一阶段论文或系统原型，建议先从以下 12 个 skill 开始，因为它们覆盖检测—定位—恢复闭环，且在 Kubernetes 上较容易做真实实验。

### 检测（4 个）
1. 指标异常检测 Skill
2. Kubernetes 事件突发检测 Skill
3. 配置变更关联检测 Skill
4. 任务卡生成 Skill

### 根因定位（4 个）
5. Pod/Deployment 状态诊断 Skill
6. Top-K 根因候选生成 Skill
7. 资源瓶颈定位 Skill
8. 故障证据摘要 Skill

### 恢复（4 个）
9. Deployment 重启恢复 Skill
10. 配置回滚 Skill
11. 镜像/配置修补 Skill
12. 恢复后隐藏验证 Skill

这一组 skill 的优点是：
- 覆盖 end-to-end 流程；
- 容易和现有 Prometheus、Loki、Jaeger、kubectl、Helm、Argo CD 集成；
- 同时包含只读 skill 与有副作用 skill，便于研究安全门控；
- 可以较自然地形成 benchmark task families。

---

## 7. 对应到 OpsSkill 的建议落地方式

在 OpsSkill 框架中，可以将上述 skill 进一步分为三类：

### 7.1 Observation Skills
- 主要读取指标、日志、trace、events、配置变更
- 风险等级低
- 主要用于 detection 和部分 RCA

### 7.2 Analysis Skills
- 主要负责证据融合、根因候选生成、影响面分析、task card / root-cause card 生成
- 可能调用 LLM，但不应直接修改环境
- 适合作为中间编译层

### 7.3 Action Skills
- 直接修改 Kubernetes 或 GitOps 状态
- 必须带前置条件、rollback、risk label 和 hidden verification
- 是安全机制与论文创新的重点

---

## 8. 论文中可直接使用的表述

你可以在论文中将智能运维 workflow 描述为：

> 一个完整的自治运维系统应至少覆盖故障检测、根因定位和故障恢复三个阶段。不同于将运维任务视为单次命令生成问题，本文将每一阶段进一步拆解为一组可复用、可组合的 skill，并通过结构化 skill 表示将跨阶段信息在 detection、diagnosis 和 remediation 之间传递。

也可以进一步强调：

> 在这一 workflow 中，检测 skill 负责从多源观测中发现异常并生成任务卡；定位 skill 负责形成根因候选与证据摘要；恢复 skill 负责在安全约束下执行修复、触发回滚并进行隐藏验证。这样的分层技能体系更符合真实智能运维系统的工作方式，也更便于进行 benchmark、复用与持续优化。
