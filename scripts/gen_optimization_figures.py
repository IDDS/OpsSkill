#!/usr/bin/env python3
"""Generate publication-quality figures and LaTeX tables for the
skill optimization before/after comparison.

Outputs:
  - fig_optimization_comparison.pdf/png  (grouped bar chart: S₀ vs S₁ score)
  - fig_structural_enrichment.pdf/png    (stacked bar: precond/rollback/hidden added)
  - tab_optimization_comparison.tex      (LaTeX table)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH    = PROJECT_ROOT / "results" / "optimization_experiment.json"
FIG_DIR      = PROJECT_ROOT / "results" / "figures"
TAB_DIR      = PROJECT_ROOT / "results" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)

# ── Load data ──
with DATA_PATH.open() as f:
    data = json.load(f)

# Style
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Friendly scenario labels
LABELS = {
    "F1-rbac-restriction": "F1\nRBAC",
    "F2-resource-missing": "F2\nResource",
    "F3-rollout-timeout":  "F3\nTimeout",
    "F4-readiness-failure":"F4\nReadiness",
    "F5-crd-missing":      "F5\nCRD",
    "F6-command-not-found": "F6\nCommand",
}

scenarios = [d["scenario"] for d in data]
labels = [LABELS[s] for s in scenarios]
s0_scores = [d["s0_score"] for d in data]
s1_scores = [d["s1_score"] for d in data]
deltas = [d["score_delta"] for d in data]

# ════════════════════════════════════════════════════════════════
# Figure 1: Score comparison (S₀ vs S₁)
# ════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 4.5))

x = np.arange(len(scenarios))
w = 0.32

bars0 = ax.bar(x - w/2, s0_scores, w, label="$S_0$ (Initial Skill)",
               color="#E74C3C", alpha=0.85, edgecolor="white", linewidth=0.8)
bars1 = ax.bar(x + w/2, s1_scores, w, label="$S_1$ (After Optimization)",
               color="#2ECC71", alpha=0.85, edgecolor="white", linewidth=0.8)

# Add value labels
for bar in bars0:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.02,
            f"{h:.0%}", ha="center", va="bottom", fontsize=8.5, color="#C0392B", fontweight="bold")
for bar in bars1:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.02,
            f"{h:.0%}", ha="center", va="bottom", fontsize=8.5, color="#27AE60", fontweight="bold")

# Delta annotations
for i, delta in enumerate(deltas):
    if delta > 0:
        ax.annotate(f"+{delta:.0%}",
                    xy=(x[i] + w/2, s1_scores[i] + 0.06),
                    fontsize=7.5, ha="center", color="#1A5276",
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#1A5276", lw=0.8),
                    xytext=(x[i] + w/2, s1_scores[i] + 0.14))

ax.set_ylabel("Score")
ax.set_title("Skill Optimization: Before vs After ($S_0 \\to S_1$)")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(0, 1.0)
ax.legend(loc="upper right")
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

fig.tight_layout()
fig.savefig(FIG_DIR / "fig_optimization_comparison.pdf")
fig.savefig(FIG_DIR / "fig_optimization_comparison.png")
plt.close(fig)
print(f"[OK] fig_optimization_comparison saved")


# ════════════════════════════════════════════════════════════════
# Figure 2: Structural enrichment (precond / rollback / hidden)
# ════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [3, 2]})

# Left: stacked bars showing before / added counts
ax = axes[0]
precond_before = [d["precond_before"] for d in data]
precond_added  = [d["precond_added"] for d in data]
rollback_before = [d["rollback_before"] for d in data]
rollback_added  = [d["rollback_added"] for d in data]
hidden_before  = [d["hidden_before"] for d in data]
hidden_added   = [d["hidden_added"] for d in data]

x = np.arange(len(scenarios))
w = 0.22

# Preconditions
ax.bar(x - w, precond_before, w, label="Precond (existing)", color="#3498DB", alpha=0.7)
ax.bar(x - w, precond_added, w, bottom=precond_before, label="Precond (+added)", color="#3498DB", alpha=1.0, hatch="//")
# Rollback
ax.bar(x, rollback_before, w, label="Rollback (existing)", color="#E67E22", alpha=0.7)
ax.bar(x, rollback_added, w, bottom=rollback_before, label="Rollback (+added)", color="#E67E22", alpha=1.0, hatch="//")
# Hidden
ax.bar(x + w, hidden_before, w, label="Hidden (existing)", color="#9B59B6", alpha=0.7)
ax.bar(x + w, hidden_added, w, bottom=hidden_before, label="Hidden (+added)", color="#9B59B6", alpha=1.0, hatch="//")

ax.set_ylabel("Component Count")
ax.set_title("Structural Enrichment by $\\Delta_\\sigma(S)$")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend(fontsize=8, ncol=2, loc="upper right")
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Right: summary pie of edit types
ax2 = axes[1]
total_precond = sum(precond_added)
total_rollback = sum(rollback_added)
total_hidden = sum(hidden_added)
total_no_change = len(data) - (1 if total_precond else 0) - (1 if total_rollback else 0) - (1 if total_hidden else 0)

sizes = [total_precond, total_rollback, total_hidden]
labels_pie = [
    f"Precondition\n(+{total_precond})",
    f"Rollback\n(+{total_rollback})",
    f"Hidden Check\n(+{total_hidden})",
]
colors_pie = ["#3498DB", "#E67E22", "#9B59B6"]
explode = (0.05, 0.05, 0.05)

# Filter out zero values
non_zero = [(s, l, c, e) for s, l, c, e in zip(sizes, labels_pie, colors_pie, explode) if s > 0]
if non_zero:
    sz, lb, cl, ex = zip(*non_zero)
    wedges, texts, autotexts = ax2.pie(
        sz, labels=lb, colors=cl, explode=ex,
        autopct=lambda pct: f"{int(round(pct * sum(sz) / 100))}",
        startangle=90, textprops={"fontsize": 10}
    )
    for at in autotexts:
        at.set_fontweight("bold")
        at.set_fontsize(12)
ax2.set_title("Total Structural Edits")

fig.tight_layout()
fig.savefig(FIG_DIR / "fig_structural_enrichment.pdf")
fig.savefig(FIG_DIR / "fig_structural_enrichment.png")
plt.close(fig)
print(f"[OK] fig_structural_enrichment saved")


# ════════════════════════════════════════════════════════════════
# Figure 3: Optimization iteration waterfall
# ════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))

# Show the failure→signature→edit→improvement flow
failure_labels = [d["failure_type"].replace("_", "\n") for d in data]
improvements = [d["improvement"] for d in data]

# Waterfall: S₀ score → delta → S₁ score
y_pos = np.arange(len(data))[::-1]
bar_h = 0.6

# S₀ bars (red)
ax.barh(y_pos, s0_scores, bar_h, color="#E74C3C", alpha=0.8, label="$S_0$ Score")
# Delta bars (green extension)
for i in range(len(data)):
    if deltas[i] > 0:
        ax.barh(y_pos[i], deltas[i], bar_h, left=s0_scores[i],
                color="#2ECC71", alpha=0.8)

# Annotations
for i in range(len(data)):
    # S₀ label
    if s0_scores[i] > 0.05:
        ax.text(s0_scores[i] / 2, y_pos[i], f"{s0_scores[i]:.0%}",
                ha="center", va="center", fontsize=9, color="white", fontweight="bold")
    # Delta label
    if deltas[i] > 0:
        ax.text(s0_scores[i] + deltas[i] / 2, y_pos[i], f"+{deltas[i]:.0%}",
                ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    # Improvement text
    if improvements[i]:
        ax.text(s1_scores[i] + 0.02, y_pos[i],
                improvements[i], ha="left", va="center", fontsize=7.5, color="#2C3E50")

ax.set_yticks(y_pos)
ax.set_yticklabels([f"{d['scenario']}\n({d['failure_type']})" for d in data], fontsize=8)
ax.set_xlabel("Score")
ax.set_title("Optimization Improvement: $\\Delta_\\sigma$ Applied to Each Failure Type")
ax.set_xlim(0, 1.05)
ax.grid(axis="x", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Legend
red_patch = mpatches.Patch(color="#E74C3C", alpha=0.8, label="$S_0$ (Before)")
green_patch = mpatches.Patch(color="#2ECC71", alpha=0.8, label="$\\Delta$ Improvement")
ax.legend(handles=[red_patch, green_patch], loc="lower right")

fig.tight_layout()
fig.savefig(FIG_DIR / "fig_optimization_waterfall.pdf")
fig.savefig(FIG_DIR / "fig_optimization_waterfall.png")
plt.close(fig)
print(f"[OK] fig_optimization_waterfall saved")


# ════════════════════════════════════════════════════════════════
# LaTeX Table: Optimization comparison
# ════════════════════════════════════════════════════════════════
tex_lines = [
    r"\begin{table}[t]",
    r"\centering",
    r"\caption{Skill optimization before/after comparison. $S_0$: initial skill under adversarial failure; $S_1$: after applying $\Delta_\sigma(S)$.}",
    r"\label{tab:optimization}",
    r"\small",
    r"\begin{tabular}{lllccccc}",
    r"\toprule",
    r"\textbf{Scenario} & \textbf{Failure Type} & \textbf{$\Delta_\sigma$ Edit} & \textbf{Score$_0$} & \textbf{Score$_1$} & \textbf{$\Delta$Score} & \textbf{Precond} & \textbf{Hidden} \\",
    r"\midrule",
]

edit_map = {
    "RBAC_DENIED": "+RBAC check",
    "RESOURCE_NOT_FOUND": "+existence check",
    "ROLLOUT_TIMEOUT": "+rollback",
    "READINESS_NOT_MET": "+readiness signal",
    "CRD_MISSING": "+CRD check",
    "COMMAND_NOT_FOUND": "+tool check",
}

for d in data:
    name = d["scenario"].replace("_", r"\_")
    ft = d["failure_type"].replace("_", r"\_")
    edit = edit_map.get(d["failure_type"], "—")
    s0 = f"{d['s0_score']:.0%}".replace("%", r"\%")
    s1 = f"{d['s1_score']:.0%}".replace("%", r"\%")
    delta_str = f"+{d['score_delta']:.0%}".replace("%", r"\%") if d["score_delta"] > 0 else r"0\%"
    delta = delta_str
    precond = f"{d['precond_before']}$\\to${d['precond_after']}"
    hidden = f"{d['hidden_before']}$\\to${d['hidden_after']}"
    tex_lines.append(f"  {name} & {ft} & {edit} & {s0} & {s1} & {delta} & {precond} & {hidden} \\\\")

# Average row
avg_s0 = sum(d["s0_score"] for d in data) / len(data)
avg_s1 = sum(d["s1_score"] for d in data) / len(data)
avg_delta = avg_s1 - avg_s0
tex_lines.append(r"\midrule")
tex_lines.append(f"  \\textbf{{Average}} & — & — & {avg_s0:.0%} & {avg_s1:.0%} & +{avg_delta:.0%} & — & — \\\\".replace("%", r"\%"))

tex_lines.extend([
    r"\bottomrule",
    r"\end{tabular}",
    r"\end{table}",
])

tab_path = TAB_DIR / "optimization_comparison.tex"
tab_path.write_text("\n".join(tex_lines), encoding="utf-8")
print(f"[OK] {tab_path.relative_to(PROJECT_ROOT)}")


# ════════════════════════════════════════════════════════════════
# LaTeX Table: Δ_σ mapping (failure type → structural edit)
# ════════════════════════════════════════════════════════════════
mapping_lines = [
    r"\begin{table}[t]",
    r"\centering",
    r"\caption{Failure signature to structural edit mapping ($\Delta_\sigma$).}",
    r"\label{tab:delta-sigma}",
    r"\small",
    r"\begin{tabular}{lll}",
    r"\toprule",
    r"\textbf{Failure Type $\sigma$} & \textbf{Structural Edit $\Delta_\sigma(S)$} & \textbf{Target Component} \\",
    r"\midrule",
    r"RBAC\_DENIED & Add \texttt{kubectl auth can-i} check & Precondition \\",
    r"RESOURCE\_NOT\_FOUND & Add resource existence probe & Precondition \\",
    r"ROLLOUT\_TIMEOUT & Add \texttt{rollout undo} entry & Rollback \\",
    r"READINESS\_NOT\_MET & Add pod-readiness jsonpath signal & Hidden Check \\",
    r"CRD\_MISSING & Add CRD existence probe & Precondition \\",
    r"COMMAND\_NOT\_FOUND & Add tool availability check & Precondition \\",
    r"\bottomrule",
    r"\end{tabular}",
    r"\end{table}",
]

mapping_path = TAB_DIR / "delta_sigma_mapping.tex"
mapping_path.write_text("\n".join(mapping_lines), encoding="utf-8")
print(f"[OK] {mapping_path.relative_to(PROJECT_ROOT)}")

print("\n[DONE] All optimization figures and tables generated.")
