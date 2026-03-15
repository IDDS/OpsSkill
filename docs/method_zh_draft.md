# 方法初稿（中文）

## 4 方法

### 4.1 方法概览与核心创新

OpsSkill 的核心目标不是让模型直接输出一段运维命令，而是学习一个**可编译、可约束执行、可验证、可优化**的技能闭环。与现有 ReAct 式或模板检索式方法相比，本文的方法具有一个关键实现原则：**skill 生成、验证、优化和调度四个环节均允许 LLM 或 agent 参与，但所有高风险执行都必须经过受控执行器。** 在这一原则下，本文的方法具有五个明确的创新点：

1. **约束感知技能编译（Constraint-Aware Skill Compilation）**：将任务卡与环境能力画像联合映射为带类型的技能对象，而非自由命令序列。
2. **分层技能调度智能体（Hierarchical Skill Orchestration Agent）**：由 manager agent 在 detection、diagnosis 与 recovery 三阶段之间进行 skill 选择与切换，而不是固定单技能执行。
3. **风险预算门控执行（Risk-Budgeted Policy Gating）**：将运维动作建模为受 blast-radius 约束的策略执行问题，在动作真正发生前进行筛选与阻断。
4. **隐藏多信号验证（Hidden Multi-Signal Verification）**：区分技能可见验证与评测使用的隐藏验证，减少对显式检查的过拟合。
5. **结构化失败驱动优化（Failure-Signature-Driven Optimization）**：从结构化执行报告中提取失败签名，在技能空间中进行更新，而不是仅依赖自由文本反思。

因此，OpsSkill 可以被写成一个四模块闭环：

$$
x \xrightarrow{f_\theta} S \xrightarrow{g_\psi} \tau \xrightarrow{h_\phi} y \xrightarrow{u_\omega} S'.
$$

其中 $f_\theta$ 为技能编译器，$\pi$ 为 manager agent 的规划策略，$g_\psi$ 为策略门控执行器，$h_\phi$ 为隐藏验证器，$u_\omega$ 为报告驱动优化器。

在实现上，$\pi$ 可以有两种形式：

- **Heuristic planner**：基于 task card、stage、一致性标签与风险标签进行确定性 skill 排序；
- **LLM planner**：通过 OpenAI-compatible 接口调用大模型，根据 task card 与候选 skill 列表输出分阶段选择结果。

为保证系统稳健性，当 LLM planner 不可用或返回无效结果时，系统自动回退到 heuristic planner。该设计使实验可以比较不同 planner 对隐藏成功率、效率与稳定性的影响，同时不破坏系统的安全默认行为。

### 4.2 约束感知技能编译

#### 4.2.1 技能空间

我们定义技能空间 $\mathcal{S}_k$ 为所有合法技能对象的集合。任一技能

$$
S = (P, A, V, R, \rho, \eta)
$$

必须满足以下结构合法性约束：

$$
\Gamma(S) = \mathbb{I}[|A| > 0] \cdot \mathbb{I}[|V_{vis}| > 0] \cdot \mathbb{I}[\text{well-typed}(P,A,R,\eta)] = 1.
$$

这里 $\Gamma(S)$ 是一个技能合法性指示函数，`well-typed` 表示技能中的前置条件、动作参数、回滚对象与实例化参数在语义上匹配。例如，若动作作用于 Deployment，则 rollback 与 hidden checks 也应面向同一对象类型。

#### 4.2.2 编译器定义

给定任务卡 $x$ 与环境能力画像 $\kappa(E)$，技能编译器 $f_\theta$ 在技能空间中求解：

$$
f_\theta(x, \kappa(E)) = \arg\max_{S \in \mathcal{S}_k} \, \mathcal{L}_{task}(S; x) - \lambda_r \mathcal{R}_{risk}(S, \kappa(E)) - \lambda_s \mathcal{R}_{schema}(S),
$$

其中：
- $\mathcal{L}_{task}$ 衡量技能与任务卡目标的一致性；
- $\mathcal{R}_{risk}$ 衡量在当前环境能力下的潜在风险；
- $\mathcal{R}_{schema}$ 衡量技能是否偏离结构规范。

这一定义体现了本文方法的第一点创新：**技能生成不是单纯的语言建模，而是一个受结构与风险正则项约束的编译问题。**

#### 4.2.3 技能编译的自包含流程

给定任务卡后，编译器按以下步骤工作：

1. 从 $d,c,g$ 中抽取目标对象、目标状态与候选动作族；
2. 从 $\kappa(E)$ 中抽取权限、对象、观测与工具能力；
3. 生成候选前置条件集合 $P$；
4. 生成动作序列 $A$ 及其回滚计划 $R$；
5. 生成显式验证器 $V_{vis}$；
6. 为 benchmark 或评测器保留隐藏验证提示 $V_{hid}$；
7. 为技能附加风险预算 $\rho$ 与实例化参数 $\eta$；
8. 对技能执行合法性检查，若失败则重新编译或降级为只读技能。

### 4.3 风险预算门控执行

### 4.2.4 Manager Agent 与 Planner

给定技能库 $\mathcal{K}$，manager agent 首先在每个阶段上选择一组候选技能：

$$
\Pi_t = \pi(x, \kappa(E), \mathcal{K}, t), \qquad t \in \{\text{detection}, \text{diagnosis}, \text{recovery}\}.
$$

其中 $\Pi_t$ 表示阶段 $t$ 上选中的技能子集。planner 的优化目标不是直接输出命令，而是最大化 skill 选择与任务卡的一致性，同时满足阶段约束与安全约束。对于 LLM planner，我们将 skill 选择建模为一个受限排序问题：

$$
\pi_{llm} = \arg\max_{\Pi_t \subseteq \mathcal{K}_t} \; \mathcal{A}(\Pi_t, x) - \lambda_m \mathcal{M}(\Pi_t),
$$

其中 $\mathcal{A}$ 表示所选 skill 与任务卡的语义匹配程度，$\mathcal{M}$ 表示 mutating skill 带来的额外风险惩罚。当系统运行在 safe default 模式时，$\mathcal{M}$ 对变更类 skill 的惩罚足够大，使 detection 和 diagnosis 优先以只读技能完成。

#### 4.3.1 风险函数

为了形式化安全约束，我们为每个技能定义风险函数：

$$
\mathcal{B}(S, E) = w_1 b_{scope} + w_2 b_{mutation} + w_3 b_{privilege} + w_4 b_{rollback},
$$

其中：
- $b_{scope}$ 衡量作用域风险，如 cluster-wide 与 namespace-local 的差异；
- $b_{mutation}$ 衡量动作是否实际修改环境；
- $b_{privilege}$ 衡量所需权限级别；
- $b_{rollback}$ 衡量回滚缺失或回滚不充分带来的风险。

#### 4.3.2 门控器定义

策略门控器 $g_\psi$ 决定技能是否可执行：

$$
g_\psi(S, \kappa(E), \Omega) = \mathbb{I}[P(S, E)=1] \cdot \mathbb{I}[\mathcal{B}(S,E) \le b_{max}] \cdot \mathbb{I}[\text{policy}(S,\Omega)=1].
$$

只有当三项同时满足时，技能才会进入执行阶段。否则系统输出阻断报告而非盲目尝试。

这一设计对应本文的第二点创新：**将自治运维建模为显式的风险受限决策，而非默认所有生成动作都可执行。**

#### 4.3.3 理论命题 1

在假设风险函数 $\mathcal{B}$ 对不安全事件概率单调的条件下，若门控器只允许满足 $\mathcal{B}(S,E) \le b_{max}$ 的技能执行，则任一执行策略的经验不安全动作率满足上界收缩：

$$
\hat{U}_{gated} \le \hat{U}_{ungated}.
$$

该命题虽然是弱形式的，但说明引入显式风险预算后，系统至少不会增加经验上的高风险动作比例。论文实验可将其作为经验验证命题而非严格定理。

### 4.4 隐藏多信号验证器

#### 4.4.1 双层验证机制

对技能 $S$ 的执行轨迹 $\tau$，我们区分两类验证：

$$
V_{vis}(\tau) \in \{0,1\}, \qquad V_{hid}(\tau) \in [0,1].
$$

$V_{vis}$ 表示技能自身可见的显式验证，例如 rollout 状态；$V_{hid}$ 表示由独立评测器计算的真实完成度，例如对象状态、事件流、服务连通性与 SLO 的综合结果。

我们将隐藏验证器写为：

$$
V_{hid}(\tau) = \sum_{j=1}^{M} \alpha_j v_j(\tau), \qquad \sum_{j=1}^{M} \alpha_j = 1,
$$

其中 $v_j$ 是不同信号上的评分函数，$\alpha_j$ 为权重。

#### 4.4.2 假阳性差距

定义假阳性差距为：

$$
\Delta_{fp} = \mathbb{E}[V_{vis}(\tau)] - \mathbb{E}[V_{hid}(\tau)].
$$

若 $\Delta_{fp}$ 很大，则说明方法主要学会了“通过显式检查”，而没有真正恢复系统。本文方法的第三个创新正在于：**把隐藏验证显式纳入目标与评测，从而避免 skill generator 对可见检查过拟合。**

#### 4.4.3 理论命题 2

若优化目标中显式加入 $-\lambda_{fp} \Delta_{fp}$ 项，则在其他因素不变时，最优策略倾向于选择在更多隐藏信号上稳定通过的技能，而非仅在显式检查上通过的技能。该命题给出本文为什么能提升真实成功率的理论动机。

### 4.5 结构化失败驱动优化

#### 4.5.1 执行报告表示

每次执行后，系统生成报告

$$
r(\tau) = (P_{res}, A_{res}, V_{vis}^{res}, V_{hid}^{res}, R_{res}, \sigma),
$$

其中 $\sigma$ 为失败签名集合。本文使用的失败签名包括 `RBAC_DENIED`、`RESOURCE_NOT_FOUND`、`ROLLOUT_TIMEOUT`、`READINESS_NOT_MET`、`CRD_MISSING`、`POLICY_BLOCKED` 等。

#### 4.5.2 技能更新算子

与文本反思方法不同，本文在技能空间上定义更新算子：

$$
u_\omega(S, r(\tau)) = \Pi_{\mathcal{S}_k}\big(S + \Delta_{\sigma}(S)\big),
$$

其中 $\Delta_{\sigma}(S)$ 表示由失败签名驱动的结构化编辑，例如：

- 对 `RESOURCE_NOT_FOUND` 添加或强化前置条件；
- 对 `RBAC_DENIED` 收紧动作范围或显式补充权限依赖；
- 对 `ROLLOUT_TIMEOUT` 增加中间检查与更强回滚；
- 对 `READINESS_NOT_MET` 增加隐藏验证信号或细化动作粒度。

$\Pi_{\mathcal{S}_k}$ 是投影算子，用于确保更新后的技能仍然位于合法技能空间中。

#### 4.5.3 理论命题 3

若失败签名到结构化编辑的映射 $\Delta_{\sigma}$ 能在期望上减少相应失败模式再次发生的概率，则序列 $\{S_t\}$ 在经验风险上满足非增趋势：

$$
\mathbb{E}[\mathcal{L}_{fail}(S_{t+1})] \le \mathbb{E}[\mathcal{L}_{fail}(S_t)].
$$

该命题说明：只要失败签名具备稳定语义，结构化技能优化比自由文本反思更容易得到可重复、可分析的改进。

### 4.6 联合优化目标

综合前述模块，我们将整体目标写为：

$$
\max_{\theta,\psi,\omega} \, \mathbb{E}[V_{hid}(\tau)] - \lambda_u \mathbb{E}[U] - \lambda_b \mathbb{E}[\mathcal{B}(S,E)] - \lambda_r \mathbb{E}[R_b] - \lambda_c \mathbb{E}[C] - \lambda_t \mathbb{E}[T] - \lambda_{fp}\Delta_{fp},
$$

subject to

$$
\Gamma(S)=1, \qquad g_\psi(S,\kappa(E),\Omega)=1 \; \text{for execution.}
$$

这一目标体现了本文的理论创新：**将 skill generation、safe execution、hidden verification 与 report-driven optimization 统一到同一个约束风险最优化框架中。**

### 4.7 自包含算法描述

为便于论文复现，我们将 OpsSkill 的一次迭代写成如下过程：

1. 输入任务卡 $x$、环境 $E$ 与约束 $\Omega$；
2. 探测环境能力，得到 $\kappa(E)$；
3. 调用编译器 $f_\theta(x,\kappa(E))$ 生成候选技能 $S$；
4. 检查技能合法性 $\Gamma(S)$；
5. 调用门控器 $g_\psi$ 判断技能是否可执行；
6. 若被阻断，则输出阻断报告；否则执行技能并得到轨迹 $\tau$；
7. 计算显式验证 $V_{vis}(\tau)$ 与隐藏验证 $V_{hid}(\tau)$；
8. 生成执行报告 $r(\tau)$ 与失败签名 $\sigma$；
9. 使用优化器 $u_\omega$ 更新技能得到 $S'$；
10. 将 $S'$ 写回 skill bank，用于后续任务复用或下一轮实验。

这一过程是自包含的，因为每个模块的输入、输出与优化目标都已形式化给出，且不依赖特定实现细节。

### 4.8 方法优势总结

相较于通用 Agent 方法，OpsSkill 在方法与理论上有三层更强的贡献：

1. **方法创新**：提出了约束感知技能编译、风险预算门控、隐藏验证和结构化失败优化四模块闭环；
2. **形式化创新**：将自治运维表述为一个带结构合法性与安全预算约束的联合优化问题；
3. **分析创新**：给出关于风险门控、假阳性差距与结构化优化收益的理论命题，为实验设计和结果解释提供依据。
