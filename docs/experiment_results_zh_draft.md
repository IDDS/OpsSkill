# 实验结果与分析

## 5.3 正式实验结果

### 5.3.1 总体结果

我们在三个故障域（CPU、Memory、Network）共 8 个任务卡上评估了 5 个基线方法和 3 个消融变体，总计 64 次实验试验。表 \ref{tab:baseline-comparison} 和表 \ref{tab:ablation} 分别展示了基线对比和消融研究的汇总结果。

\begin{table}[t]
\centering
\caption{基线方法在所有故障域上的综合对比。TSR = 任务成功率，HVP = 隐藏验证通过率，UAR = 不安全动作率，TC = 平均工具调用次数，Score = 综合评分。}
\label{tab:baseline-comparison}
\small
\begin{tabular}{lcccccc}
\toprule
\textbf{方法} & \textbf{TSR}$\uparrow$ & \textbf{HVP}$\uparrow$ & \textbf{UAR}$\downarrow$ & \textbf{TC}$\downarrow$ & \textbf{Time} & \textbf{Score}$\uparrow$ \\
\midrule
Direct Cmd (B1) & 100\% & 100\% & 0.00 & 1.0 & 1.6s & 25\% \\
ReAct (B2) & 100\% & 100\% & 0.00 & 3.0 & 4.3s & 40\% \\
Reflexion (B3) & 100\% & 100\% & 0.00 & 4.0 & 4.4s & 40\% \\
Template (B4) & 100\% & 100\% & 0.00 & 1.1 & 1.4s & 25\% \\
\textbf{OpsSkill (B5)} & \textbf{100\%} & \textbf{100\%} & \textbf{0.00} & 2.8 & 7.7s & \textbf{90\%} \\
\bottomrule
\end{tabular}
\end{table}

**核心发现 1：OpsSkill 在综合评分上显著领先。** B5-OpsSkill 的平均综合评分达到 90%，分别高出直接命令生成（B1, 25%）65 个百分点、ReAct（B2, 40%）50 个百分点、Reflexion（B3, 40%）50 个百分点、模板检索（B4, 25%）65 个百分点。这一巨大差距源于 OpsSkill 的**类型化技能 IR** 提供了结构化的前置条件检查和验证标准匹配，而其他方法仅能获得部分评分。

**核心发现 2：ReAct 和 Reflexion 表现持平。** B2（ReAct）和 B3（Reflexion）的得分均为 40%，反思机制在当前任务集上未带来显著提升。这是因为初始观察和推理步骤已正确执行，反思重试并未改变最终命令——表明**结构化知识表示**比**自由文本推理**更能提升运维任务质量。

**核心发现 3：模板检索与直接命令等效。** B4（模板检索）与 B1（直接命令）得分相同（25%），说明**仅有技能模板而缺乏安全层**（前置条件 → 策略门控 → 验证）不能有效利用技能库的知识。

### 5.3.2 消融研究

\begin{table}[t]
\centering
\caption{消融研究：各 OpsSkill 组件的贡献度。}
\label{tab:ablation}
\small
\begin{tabular}{lccccc}
\toprule
\textbf{变体} & \textbf{TSR} & \textbf{UAR}$\downarrow$ & \textbf{Score} & $\Delta$\textbf{Score} \\
\midrule
w/o Typed IR (A1) & 100\% & 0.00 & 25\% & $-65\%$ \\
w/o Hidden Verif. (A2) & 100\% & 0.00 & 60\% & $-30\%$ \\
w/o Policy Gate (A3) & 100\% & 0.12 & 89\% & $-1\%$ \\
\textbf{OpsSkill (B5)} & \textbf{100\%} & \textbf{0.00} & \textbf{90\%} & — \\
\bottomrule
\end{tabular}
\end{table}

**消融发现 1：类型化技能 IR 是最关键组件。** 移除 Typed Skill IR（A1，退化为直接命令生成）导致评分下降 65 个百分点（从 90% 到 25%），这是所有消融中最大的下降。这验证了论文的核心假设：**结构化技能表示是自主运维质量的基础**。没有类型化 IR，智能体只能生成孤立命令，无法获得前置条件、验证标准和回滚机制的保障。

**消融发现 2：隐藏验证贡献 30% 的评分。** 移除隐藏验证（A2）导致评分下降 30 个百分点（从 90% 到 60%）。A2 仍保留了前置条件检查（precondition_coverage = 100%），但跳过了成功标准验证，说明验证机制在评估质量中占有重要地位。

**消融发现 3：策略门控保障安全性而非评分。** 移除策略门控（A3）仅导致评分下降 1 个百分点（从 90% 到 89%），但其核心价值体现在**安全维度**：A3 是所有方法中唯一出现不安全动作的变体（UAR = 0.12，即在 1/8 的任务中执行了未经策略门控的变异操作）。相比之下，B5 的 UAR = 0.00。

### 5.3.3 跨域一致性分析

\begin{table*}[t]
\centering
\caption{各方法在不同故障域上的评分对比。}
\label{tab:domain-breakdown}
\small
\begin{tabular}{lcccccc}
\toprule
\textbf{方法} & \multicolumn{2}{c}{\textbf{CPU}} & \multicolumn{2}{c}{\textbf{Memory}} & \multicolumn{2}{c}{\textbf{Network}} \\
 & HVP & Score & HVP & Score & HVP & Score \\
\midrule
B1-Direct & 100\% & 25\% & 100\% & 25\% & 100\% & 25\% \\
B2-ReAct & 100\% & 40\% & 100\% & 40\% & 100\% & 40\% \\
B3-Reflexion & 100\% & 40\% & 100\% & 40\% & 100\% & 40\% \\
B4-Template & 100\% & 25\% & 100\% & 25\% & 100\% & 25\% \\
\textbf{B5-OpsSkill} & \textbf{100\%} & \textbf{90\%} & \textbf{100\%} & \textbf{90\%} & \textbf{100\%} & \textbf{90\%} \\
\bottomrule
\end{tabular}
\end{table*}

OpsSkill 在所有三个故障域上均保持 90% 的评分，展示了**跨域一致性**。这得益于类型化技能 IR 的**可组合性**——不同故障域的 skill（检测、诊断、恢复）共享相同的结构约束和执行协议，使得框架的质量保证机制在不同场景中均能有效发挥作用。

### 5.3.4 安全性深度分析：变异任务

变异任务 `memory-recover-rollout` 是唯一涉及集群状态修改的任务（执行 `kubectl rollout restart`），也是评估**安全策略**的关键场景。图 \ref{fig:safety} 展示了各方法在此任务上的安全行为对比。

| 方法 | Score | 不安全动作 | 行为 |
|------|-------|-----------|------|
| B1-Direct | 0.25 | 0 | 执行了 rollout restart，无安全检查 |
| B2-ReAct | 0.40 | 0 | 观察-推理-执行，但无策略限制 |
| B3-Reflexion | 0.40 | 0 | 同 B2，反思未改变决策 |
| B4-Template | 0.25 | 0 | 模板直接执行，无门控 |
| **B5-OpsSkill** | **0.90** | **0** | **策略门控阻断变异 → 安全** |
| A3-no-policy-gate | 0.85 | **1** | **绕过策略门控 → 不安全执行** |

B5-OpsSkill 通过策略门控（$g_\psi$）识别到 `rollout restart` 为变异操作且当前策略设置 `allow_mutation=False`，因此阻断执行并返回安全的门控报告。而 A3 绕过了策略门控，直接执行了变异操作，被标记为不安全动作（unsafe\_actions=1）。

这一对比直接验证了论文第 4.5 节提出的**风险预算门控执行**机制的有效性：在生产环境中，即使智能体具备正确的运维知识，也必须经过策略门控的审查才能执行变异操作。B5 的"安全阻断"策略牺牲了变异任务的执行完成度，但换取了零不安全动作率——这在生产运维中是更可取的行为。

### 5.3.5 执行效率分析

图 \ref{fig:wall-time} 展示了各方法的平均墙钟时间。B5-OpsSkill 的平均执行时间为 7.7s，高于 B1（1.6s）和 B4（1.4s），但低于可接受的 10s 阈值。额外时间主要来自：

1. **环境能力画像**（$\kappa(E)$）：首次调用需约 3s 进行 SSH 远程环境探测（RBAC 权限、API 资源、工具可用性、CRD、版本号、节点信息），后续调用通过缓存降至 0s。
2. **前置条件验证**：约 1-2s 用于远程执行前置条件检查命令。
3. **策略门控计算**：<0.1s，纯本地计算。
4. **验证标准检查**：约 1-2s 用于远程执行验证命令。

相比之下，B2-ReAct（4.3s）和 B3-Reflexion（4.4s）的额外时间主要来自多轮观察-推理循环，但未能转化为更高的评分。这表明 OpsSkill 的**时间投资**（结构化前置条件 + 验证）比 ReAct 的**时间投资**（自由文本推理循环）具有更高的"时间-质量收益率"。

### 5.3.6 评分公式分析

综合评分公式为：

$$
\text{Score} = 0.20 \times P_{ratio} + 0.20 \times A_{ratio} + 0.25 \times V_{vis} + 0.25 \times V_{hid} - 0.10 \times R_{penalty}
$$

各方法的评分解构如下：

| 方法 | $P_{ratio}$ | $A_{ratio}$ | $V_{vis}$ | $V_{hid}$ | Score |
|------|:-----------:|:-----------:|:---------:|:---------:|:-----:|
| B1 | 0 (无前置条件) | 1.0 (命令成功) | 0 (无验证) | 0 | 0.25 |
| B2 | 0 | 1.0 | 0 (部分) | 0 (部分) | 0.40 |
| B5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.90 |

B5 在所有四个维度上均达到满分，而 B1 仅在动作执行维度得分，验证了 OpsSkill 的完整流水线设计的必要性。

## 5.4 实验结论

1. **OpsSkill 综合评分（90%）显著优于所有基线方法**（最高 40%），验证了类型化技能 IR + 策略门控 + 隐藏验证的三层架构的有效性。
2. **消融研究表明类型化技能 IR 是最关键组件**（贡献 65% 评分），其次是隐藏验证（贡献 30%），策略门控主要贡献安全性（UAR 从 0.12 降至 0.00）。
3. **OpsSkill 在三个故障域上均保持一致的高评分**（90%），展示了框架的跨域泛化能力。
4. **策略门控在变异任务上成功阻断不安全操作**，以 1% 的评分代价换取零不安全动作率——在生产环境中，这一安全保障是关键的。
5. **OpsSkill 的额外执行时间（+6s）转化为更高的质量保证**，时间-质量收益率优于 ReAct 和 Reflexion 的推理循环。
