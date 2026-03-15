# 端到端智能运维工作流研究与技能设计（中文）

本文将端到端智能运维流程划分为三个核心阶段：故障检测（fault detection）、根因分析/定位（root cause analysis / localization）、故障恢复/处置（recovery / remediation）。目标不是泛泛描述 AIOps，而是为 `OpsSkill` 这类系统沉淀可执行、可验证、可复用的技能种子，尤其面向 Kubernetes / 云原生场景。

## 1. 总体结论：适合构建技能库的三阶段框架

### 阶段 A：故障检测
该阶段的目标是从海量信号中确认“是否真的发生故障、影响谁、优先级多高、下一步应从哪里开始查”。适合拆分为六类技能：

1. **告警接入与规范化**：统一 Prometheus、云监控、APM、日志平台、值班系统的信号格式。
2. **症状确认与去重**：区分真实故障、重复告警、瞬时抖动和噪声。
3. **对象级健康检查**：将异常映射到 Pod、Deployment、Service、Node、Ingress、Job 等 Kubernetes 对象。
4. **影响范围评估**：识别受影响命名空间、服务链路、租户和 SLO/SLA。
5. **变更相关性检查**：把告警与最近镜像发布、配置变更、扩缩容、策略变更关联起来。
6. **事件打包与交接**：输出供 RCA 阶段使用的结构化证据包，而不是只输出一段文本结论。

### 阶段 B：根因分析 / 定位
该阶段的目标是回答“为什么坏了、坏在什么对象、哪一层最可能是真正根因、证据链是否足够支撑处置”。适合拆分为六类技能：

1. **证据主轴选择**：按 metrics / logs / traces / events / config / topology 选择主证据面。
2. **对象内诊断**：定位容器崩溃、探针失败、资源耗尽、配置缺失、镜像错误等对象内问题。
3. **依赖链定位**：判断问题是在上游依赖、网络路径、服务发现、网关还是数据面。
4. **变更归因**：将异常与最近 GitOps 提交、Helm 升级、ConfigMap/Secret 变更或 RBAC 修改绑定。
5. **约束与策略定位**：识别 NetworkPolicy、Admission、PodSecurity、RBAC、Quota、LimitRange 等约束导致的失败。
6. **根因假设排序**：输出带置信度的候选根因、受影响对象和推荐处置前置条件。

### 阶段 C：故障恢复 / 处置
该阶段的目标是回答“在风险可控前提下，应该执行什么动作、如何验证是否修好、失败后如何回滚”。适合拆分为六类技能：

1. **处置动作选择**：在 restart、rollback、patch、reconcile、failover、限流、隔离中选最低风险方案。
2. **执行前门控**：检查 RBAC、作用域、dry-run 可行性、依赖健康、是否存在回滚点。
3. **低风险恢复动作**：优先选择 rollout restart、scale restore、job rerun、GitOps reconcile 等可逆动作。
4. **配置/策略修复**：执行 Service selector、镜像 tag、环境变量、NetworkPolicy、Ingress 路由等修复。
5. **恢复后验证**：验证对象状态、事件、日志、延迟、错误率、SLO burn rate 是否恢复。
6. **回滚与记录同步**：失败时回滚；成功后同步 incident 记录、变更记录与技能报告。

## 2. 阶段 A：故障检测技能设计

### 2.1 初始技能清单（建议优先做 8 个）

| 技能 | 典型输入 | 推荐工具 | 输出 | 关键安全点 |
| --- | --- | --- | --- | --- |
| 告警规范化与去重 | Alertmanager / CloudWatch / Datadog / PagerDuty 告警 payload | Prometheus Alertmanager API、Webhook、事件总线 | 标准化 incident seed，含时间、对象、严重级别、来源 | 防止重复告警触发重复自动化；保留原始事件 ID |
| SLO/Burn-rate 二次确认 | 服务名、错误率、延迟、SLO 阈值、时间窗 | Prometheus、Grafana、Google SRE burn-rate 规则 | 是否达到升级门槛、持续时长、建议优先级 | 避免把短时尖峰误判成故障；窗口必须可配置 |
| Kubernetes 工作负载健康扫面 | namespace、label selector、对象类型 | `kubectl get/describe`、kube-state-metrics、metrics-server | 异常对象列表，如 `CrashLoopBackOff`、`Pending`、`ImagePullBackOff` | 默认只读；限定 namespace，避免跨租户枚举 |
| 事件洪峰与异常事件聚类 | namespace、时间范围、事件流 | Kubernetes Events、Loki、Elasticsearch/OpenSearch | 高频异常事件摘要与 Top-K reason | 避免全量拉取长期事件造成 API 压力 |
| 日志签名抽样与聚类 | Pod 列表、时间窗、错误关键字 | Loki、OpenSearch、Datadog Logs | 代表性错误签名、出现频率、受影响 Pod 集合 | 日志可能含敏感信息；需脱敏与采样 |
| Trace/调用链热点确认 | service、延迟阈值、trace 时间窗 | OpenTelemetry、Jaeger、Tempo、Kiali | 异常 span、热点服务、首个明显退化点 | 不主动开启高开销追踪；只读取已有追踪数据 |
| 变更相关性检测 | 最近发布记录、ConfigMap 版本、GitOps 提交、Helm revision | Argo CD、Flux、Helm、CI/CD API | “异常是否紧邻变更”结论与候选变更集 | 不把相关性直接当因果；需保留不确定性 |
| 故障证据包生成 | 上述技能输出 | 任务编排器、对象存储、报告模块 | 面向 RCA 的结构化证据包：症状、影响范围、时间线、候选变更 | 证据包需最小化敏感信息并记录数据来源 |

### 2.2 代表性论文

- `DeCaf: diagnosing and triaging performance issues in large-scale cloud services`（ICSE-SEIP 2020）：强调真实云故障处理首先是 diagnosis + triage 流水线。
- `Neural Knowledge Extraction From Cloud Service Incidents`（ICSE-SEIP 2021）：说明 incident 文本与调查记录可提取为结构化运维知识。
- `Mining root cause knowledge from cloud service incident investigations for AIOps`（ICSE-SEIP 2022）：适合作为从历史 incident 沉淀检测/分诊先验的桥梁论文。
- `DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning`（CCS 2017）：代表日志异常检测范式，可支撑“日志签名触发检测技能”。

### 2.3 代表性产品与开源工具

- **商业产品**：Datadog Watchdog、Dynatrace Davis AI、New Relic AI、Splunk ITSI、Google Cloud Operations、Amazon CloudWatch Anomaly Detection。
- **开源工具**：Prometheus、Alertmanager、Grafana、Loki、OpenTelemetry Collector、kube-state-metrics、BotKube。
- **Kubernetes 相关性**：最适合覆盖 Pod 生命周期异常、节点压力、服务端点缺失、Ingress 5xx、HPA 抖动、发布后错误率升高等检测任务。

## 3. 阶段 B：根因分析 / 定位技能设计

### 3.1 初始技能清单（建议优先做 8 个）

| 技能 | 典型输入 | 推荐工具 | 输出 | 关键安全点 |
| --- | --- | --- | --- | --- |
| `CrashLoopBackOff` 根因提取 | Pod 名称、容器日志、上一实例退出码、事件 | `kubectl describe/logs --previous`、Loki | 根因类别：配置缺失 / 启动命令错误 / 探针失败 / 依赖不可达 | 默认只读；避免执行 `kubectl exec` 进入容器做侵入式探查 |
| OOM / CPU 节流定位 | 容器资源配额、usage、throttling 指标 | cAdvisor、Prometheus、kubectl top、Pyroscope/Parca | 是 requests/limits 配置问题、真实负载峰值还是内存泄漏线索 | 避免开启高频 profiling；必要时需要门控授权 |
| Service selector / Endpoint 失配定位 | Service、Endpoints、Pod labels、Deployment labels | `kubectl get svc,endpoints,pods -o yaml` | 失配对象、缺失 label/port、受影响流量路径 | 只读分析即可；不要直接 patch |
| DNS / NetworkPolicy 路径诊断 | Service 名、Pod DNS、egress/ingress 策略、连接失败日志 | CoreDNS 日志、`kubectl describe networkpolicy`、CNI 可观测工具、Hubble/Cilium | 问题位于 DNS、策略阻断、跨命名空间访问或服务发现层 | 避免大量主动探测流量；限制为白名单目标 |
| Ingress / Gateway 路由定位 | Ingress/Gateway、VirtualService、后端服务、HTTP 5xx/404 | NGINX Ingress 日志、Gateway API 对象、Istio/Kiali | 路由规则、host/path、TLS 或后端端口失配结论 | 不直接改网关规则；先生成诊断结论 |
| RBAC / 凭据失败定位 | `Forbidden` 错误、ServiceAccount、RoleBinding、Secret 挂载状态 | `kubectl auth can-i`、审计日志、事件、Secret/SA 对象 | 权限缺失点、主体、作用域和最小补权建议 | 不自动扩大权限；输出最小权限补丁建议 |
| 配置漂移与 GitOps 归因 | live state、Git desired state、Helm release、最近 commit | Argo CD diff、Flux、Helm history、`kubectl diff` | 哪个对象漂移、漂移字段、疑似来源变更 | 只读 diff；不能在未门控时直接 reconcile |
| 多信号因果证据组装 | metrics、logs、events、traces、变更时间线 | 图模型/规则引擎、报告模块、Kiali/Jaeger | 带置信度的候选根因排序和“下一步恢复建议” | 必须显式保留不确定性，避免单一信号过拟合 |

### 3.2 代表性论文

- `MicroDiag: Fine-grained Performance Diagnosis for Microservice Systems`（CloudIntelligence 2021）：代表微服务细粒度诊断。
- `Actionable and interpretable fault localization for recurring failures in online service systems`（ESEC/FSE 2022）：强调“可行动、可解释”的定位结果，而非纯排名。
- `Diagnosing Performance Issues for Large-Scale Microservice Systems With Heterogeneous Graph`（IEEE TSC 2024）：代表把异构监控信号建模为图进行定位。
- `ReconRCA: Root Cause Analysis in Microservices with Incomplete Metrics`（ICWS 2025）：适合支撑“不完全可观测”下的 RCA 设计。

### 3.3 代表性产品与开源工具

- **商业产品**：Komodor、Dynatrace Distributed Tracing / Davis、Datadog APM、Splunk Observability Cloud / ITSI、Sysdig Monitor。
- **开源工具**：Jaeger、Grafana Tempo、Kiali、Pyroscope、Parca、K8sGPT、OpenSearch。
- **Kubernetes 相关性**：最适合覆盖容器启动失败、服务发现错误、配置漂移、网关配置错误、NetworkPolicy 阻断、RBAC 拒绝、资源耗尽等定位任务。

## 4. 阶段 C：故障恢复 / 处置技能设计

### 4.1 初始技能清单（建议优先做 9 个）

| 技能 | 典型输入 | 推荐工具 | 输出 | 关键安全点 |
| --- | --- | --- | --- | --- |
| 安全 `rollout restart` | Deployment 名称、namespace、健康阈值、回滚条件 | `kubectl rollout restart/status`、Argo Rollouts | 重启结果、恢复前后健康对比、失败时回滚信号 | 仅允许 namespace 内对象；必须先确认副本数与 readiness |
| 副本数 / HPA 恢复 | 当前副本数、目标副本数、HPA 最小/最大值、负载指标 | `kubectl scale`、HPA API、Prometheus | 恢复到目标容量并附验证结果 | 防止误扩缩容导致成本/雪崩；需要上下界门控 |
| 镜像版本回滚 | 当前镜像、上一个稳定 revision、发布记录 | `kubectl rollout undo`、Helm rollback、Argo CD | 已回滚的 revision、对象状态、验证报告 | 必须确认回滚点存在且兼容；对 StatefulSet 更谨慎 |
| ConfigMap / Secret 修复并触发发布 | 缺失键、错误值、引用对象、期望 checksum | `kubectl patch/apply`、Helm、Kustomize、Argo CD | 修复后的配置对象、触发重建/发布结果 | Secret 处理需脱敏；优先从 GitOps 源修复而非手工热改 |
| Service selector / port 修复 | Service、targetPort、Pod labels、Endpoint 状态 | `kubectl patch service`、`kubectl diff` | 流量恢复结果、Endpoint 恢复证明 | 修改前必须做 diff；避免误影响共享 Service |
| Job 重跑与卡死 Pod 清理 | Job 状态、失败原因、重试策略、Pod 生命周期 | `kubectl delete pod/job`、CronJob/Job API | 重跑结果、完成状态、失败日志摘要 | 不重复触发非幂等业务作业；需识别副作用 |
| Ingress / Gateway 路由回退 | host/path、后端 service、最近变更版本 | Ingress/Gateway API、Istio、Argo CD/Helm | 路由回退结果、HTTP 健康检查结果 | 先验证 blast radius；网关变更需灰度或小流量验证 |
| NetworkPolicy 回滚或最小放通 | 被阻断流量对、期望端口、作用域 | `kubectl apply`、Kyverno/OPA 预检、Cilium/Hubble | 最小变更后的连通性验证 | 严禁全开放策略；必须最小作用域、最小端口 |
| GitOps 一键对齐与漂移收敛 | live drift 详情、目标 revision、同步策略 | Argo CD sync、Flux reconcile | live state 与 desired state 对齐证明 | 需要确认 Git 仓库是可信源；避免把错误配置重新同步 |

### 4.2 代表性论文

- `AutoTSG: learning and synthesis for incident troubleshooting`（ESEC/FSE 2022）：最适合作为“从排障指南到处置计划”的近邻工作。
- `Nissist: An Incident Mitigation Copilot based on Troubleshooting Guides`（ECAI 2024）：代表基于 troubleshooting guide 的事故缓解 copilot。
- `Human-in-the-Loop Runbook Improvement with Agentic Support Automation`（CogMI 2025）：强调 runbook 自动化中的人在回路与持续改进。
- `AI-Governance and Levels of Automation for AIOps-supported System Administration`（ICCCN 2020）：为恢复阶段的分级自动化、审批和门控提供理论依据。

### 4.3 代表性产品与开源工具

- **商业产品**：Shoreline、PagerDuty Rundeck、Red Hat Ansible Automation Platform、AWS Systems Manager Automation、Azure Automation、Harness。
- **开源工具**：Argo CD、Flux、Argo Rollouts、AWX、StackStorm、Keptn、Litmus、Chaos Mesh、Kyverno、OPA Gatekeeper。
- **Kubernetes 相关性**：最适合覆盖滚动重启、版本回滚、声明式修复、GitOps 收敛、最小策略变更、恢复后验证与自动回滚。

## 5. 对 `OpsSkill` 最有价值的技能设计原则

如果目标是构建一套可执行的云原生运维技能库，优先级建议如下：

1. **先读后写**：先构建检测和定位技能，再开放恢复技能；恢复技能默认从只影响单个 namespace 的可逆动作开始。
2. **每个技能都要有结构化 I/O**：至少包含 `inputs`、`tool plan`、`expected evidence`、`success checks`、`safety checks`、`rollback`。
3. **把“工具”与“技能”区分开**：`kubectl`、Prometheus、Loki、Jaeger 只是工具；真正可复用的是“如何在约束下用这些工具完成某类任务”的技能模板。
4. **把 Kubernetes 资源语义做成一等公民**：Pod、Deployment、Service、Ingress、NetworkPolicy、RBAC、HPA、ConfigMap、Secret、GitOps revision 都应出现在技能 schema 中。
5. **输出必须能交接到下一阶段**：检测阶段输出 incident seed，定位阶段输出根因假设与处置前置条件，恢复阶段输出验证报告与回滚记录。
6. **安全默认值要写进技能本体**：namespace 作用域、只读优先、dry-run 优先、敏感信息脱敏、最小权限、最小 blast radius、失败即停。

## 6. 推荐的首批实现顺序

若希望尽快形成可评测的 `OpsSkill` 技能库，建议先做以下 12 个高价值技能：

- 检测：告警规范化与去重、Kubernetes 工作负载健康扫描、事件聚类、变更相关性检测。
- 定位：`CrashLoopBackOff` 根因提取、Service/Endpoint 失配定位、配置漂移与 GitOps 归因、RBAC 失败定位。
- 恢复：安全 `rollout restart`、镜像版本回滚、Service selector 修复、GitOps 一键对齐与漂移收敛。

这 12 个技能已经足以覆盖大量真实 Kubernetes 运维任务，并且天然适合构造成带隐藏验证的 benchmark 样例。