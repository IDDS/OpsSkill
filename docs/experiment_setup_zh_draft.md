# 实验设置（论文正式稿）

## 5.1 实验环境

### 集群配置

本文实验在一个由三个工作节点组成的 Kubernetes 集群上进行，集群运行 Kubernetes v1.33.6，容器运行时为 Docker v29.1.3（API v1.52）。三个节点分别为 `lsy-1`、`lsy-2`、`lsy-3`，各配备 8 核 CPU 与 32 GB 内存。集群通过 SSH 跳板远程访问，形式为：

```
本地 → 跳板 (222.200.180.102) → 集群主节点 (10.10.3.110)
```

实验运行在独立的命名空间 `opsskill-exp` 中，与其他工作负载隔离。

### 目标应用

我们部署了一个基于 `nginx:1.27-alpine` 的单副本 Deployment 作为目标应用（`demo-app`），配置了：
- **资源配额**：request 100m CPU / 128Mi Mem，limit 500m CPU / 256Mi Mem
- **健康检查**：liveness probe（HTTP GET /, 10s 周期）与 readiness probe（HTTP GET /, 5s 周期）
- **节点固定**：通过 `nodeSelector` 固定到 `lsy-2`，确保故障注入的确定性

### 混沌工程平台

故障注入使用 Chaos Mesh v2.8.1 完成，支持以下故障类型：
- **StressChaos**：CPU 负载注入（80% 负载，1 worker）与内存压力注入（180 MB，1 worker）
- **NetworkChaos**：网络延迟注入（120 ms 延迟，50% 相关性，30 ms 抖动，出方向）

> **注**：初始实验中使用的 Chaos Mesh v2.6.2 因内置 Docker client 版本（v1.41）与集群 Docker Engine（最低 API v1.44）不兼容，导致 StressChaos 全部失败。NetworkChaos 则因 ipset 模块兼容性问题失败。升级至 v2.8.1 后所有混沌类型均正常工作。此问题本身也验证了框架的**环境能力画像** $\kappa(E)$ 理论的必要性——skill 的可执行性依赖于环境能力约束。

### 实验模式

实验脚本支持两种模式：
| 模式 | 混沌持续时间 | 观测等待 | 用途 |
|------|------------|---------|------|
| `fast` | 25s | 5s | 调试与 pilot 验证 |
| `paper` | 90s | 15s | 正式论文数据采集 |

本节报告的结果来自 `fast` 模式 pilot 实验，后续正式实验将使用 `paper` 模式。

## 5.2 实验流程

每个故障场景（CPU / Memory / Network）执行完整的 **检测 → 诊断 → 恢复/验证** 三阶段 skill 链路：

```
[Chaos 注入] → [等待观测] → [Detection Skill] → [Diagnosis Skill] → [Recovery/Hidden Verification Skill] → [Chaos 清理]
```

### 故障场景覆盖

| 故障域 | 注入类型 | 检测 Skill | 诊断 Skill | 恢复/验证 Skill |
|--------|---------|-----------|-----------|----------------|
| CPU | StressChaos (80% load) | metric-anomaly-detection | pod-deployment-state-diagnosis | hidden-recovery-verification |
| Memory | StressChaos (180 MB) | k8s-event-burst-detection | topk-root-cause-generation | deployment-rollout-restart |
| Network | NetworkChaos (120ms delay) | config-change-correlation | — | hidden-recovery-verification |

### 评估指标

对每个 skill 执行，我们记录：
- **前置条件通过率**（Precondition Pass Rate）
- **动作执行成功率**（Action Success Rate, via exit code）
- **验证标准满足率**（Success Criteria Satisfaction Rate）
- **综合 Score** = (通过的前置条件 + 通过的验证标准) / (总前置条件 + 总验证标准) × 100%
- **回滚触发次数**
