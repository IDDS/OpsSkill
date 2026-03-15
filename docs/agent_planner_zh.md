# Manager Agent 与 Planner 设计（中文）

## 1. 为什么需要 Agent

单个 skill 只能完成局部任务，而真实智能运维流程通常需要跨阶段决策：
- 先做 detection 还是直接进入 diagnosis
- diagnosis 后是否需要 recovery
- recovery 失败后是否回滚或重新诊断

因此，OpsSkill 需要一个 manager agent 负责跨阶段 skill 编排。

## 2. Agent 架构

OpsSkill 的 agent 架构包含四层：

1. **Task Card**
   - 输入任务描述、约束和上下文
2. **Planner**
   - 从 skill bank 中选择当前阶段最合适的 skill
3. **Safe Executor**
   - 负责执行 skill，并应用 policy gate
4. **Verifier / Optimizer**
   - 验证结果并生成下一轮优化信号

## 3. 两类 Planner

### Heuristic Planner
- 无需外部 API
- 可复现、稳定、低成本
- 适合作为默认规划器和强基线

### LLM Planner
- 基于 OpenAI-compatible 接口
- 输入 task card 和候选 skills
- 输出按阶段选择的 skill 列表
- 更适合复杂任务与更强语义匹配

## 4. 安全默认策略

为了避免 planner 直接扩大风险，系统采用安全默认行为：
- detection 与 diagnosis 可默认执行
- recovery 中 mutating skills 必须显式开启
- 如果 LLM planner 不可用，则自动 fallback 到 heuristic planner

## 5. 论文中可写的实验对比

可以比较三类规划策略：
- fixed stage order + heuristic planner
- manager agent + heuristic planner
- manager agent + LLM planner

对比指标建议包括：
- hidden success
- first-pass success
- planner latency
- average selected skills per task
- unsafe action rate
- fallback frequency
