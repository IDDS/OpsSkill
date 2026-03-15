#!/usr/bin/env python3
"""Generate OpsSkill framework overview diagram (English labels for matplotlib
compatibility).  The LaTeX caption will provide the Chinese description."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import os

fig, ax = plt.subplots(1, 1, figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(-0.8, 9.7)
ax.axis("off")

# ── Colour Palette ──
C_INPUT   = "#E8F5E9"
C_COMPILE = "#E3F2FD"
C_GATE    = "#FFF3E0"
C_EXEC    = "#FCE4EC"
C_VERIFY  = "#F3E5F5"
C_OPT     = "#FFF9C4"
C_SKILL   = "#E0F7FA"
C_BORDER  = "#37474F"
C_ARROW   = "#455A64"
C_FB      = "#E65100"

# ── Helpers ──
def box(x, y, w, h, line1, line2, fc, fs1=11, fs2=8.5):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                       facecolor=fc, edgecolor=C_BORDER, lw=1.6, zorder=2)
    ax.add_patch(b)
    if line2:
        ax.text(x + w / 2, y + h / 2 + 0.18, line1, ha="center", va="center",
                fontsize=fs1, fontweight="bold", color="#212121", zorder=3)
        ax.text(x + w / 2, y + h / 2 - 0.22, line2, ha="center", va="center",
                fontsize=fs2, color="#555", zorder=3, style="italic")
    else:
        ax.text(x + w / 2, y + h / 2, line1, ha="center", va="center",
                fontsize=fs1, fontweight="bold", color="#212121", zorder=3)

def arrow(x1, y1, x2, y2, color=C_ARROW, lw=1.8, cs="arc3,rad=0"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.15",
                                color=color, lw=lw, connectionstyle=cs),
                zorder=4)

# ========== TITLE ==========
ax.text(7, 9.35, "OpsSkill Framework Overview",
        ha="center", va="center", fontsize=17, fontweight="bold",
        color="#1A237E")

# ========== Row 1 – Inputs (y ≈ 7.5) ==========
box(0.4,  7.4, 2.8, 1.1, "Task Card",
    r"$x = (d,\,c,\,g,\,\Omega,\,\mathcal{T})$", C_INPUT)
box(3.8,  7.4, 3.2, 1.1, "Env Capability Profile",
    r"$\kappa(E)=(\kappa_{rbac},\kappa_{res},\ldots)$", C_INPUT, fs2=8)
box(7.8,  7.4, 2.8, 1.1, "LLM Compiler",
    r"$f_\theta$ (DeepSeek-V3)", C_INPUT)

# ========== Row 2 – Compile (y ≈ 5.5) ==========
box(1.5, 5.3, 5.0, 1.2,
    "(1) Constraint-Aware Compilation",
    r"$f_\theta(x,\,\kappa(E)) \;\to\; S$", C_COMPILE, fs1=11.5)

# Typed Skill IR (right)
box(8.0, 5.0, 4.0, 1.8,
    "Typed Skill IR",
    r"$S=(P,A,V,R,\rho,\eta)$", C_SKILL, fs1=13, fs2=10)

# ========== Row 3 – Gate (y ≈ 3.5) ==========
box(1.5, 3.3, 5.0, 1.2,
    "(2) Risk-Budget Gated Execution",
    r"Precond + Risk $\leq b_{max}$ + Policy", C_GATE, fs1=11.5)

# ========== Row 4 – Execute (y ≈ 1.6) ==========
box(1.5, 1.4, 5.0, 1.2,
    "(3) Controlled Executor",
    r"Execute $A$ $\to$ trace $\tau=[(a_i,o_i)]$", C_EXEC, fs1=11.5)

# ========== Row 5 – Verify + Optimise (y ≈ 0) ==========
box(0.2, -0.3, 3.5, 1.2,
    "(4) Hidden Multi-Signal Verify",
    r"$V_{vis}(\tau)+V_{hid}(\tau)$", C_VERIFY, fs1=10.5)

box(4.2, -0.3, 3.5, 1.2,
    "(5) Failure-Driven Optimization",
    r"$\sigma \to \Delta_\sigma(S) \to S'$", C_OPT, fs1=10.5)

# Skill Bank
box(8.5, -0.3, 3.3, 1.2, "Skill Bank",
    "Accumulate & Reuse", C_SKILL, fs1=12)

# ========== PASS / BLOCK labels ==========
ax.text(1.0, 4.05, "PASS", ha="center", va="center", fontsize=9.5,
        fontweight="bold", color="#2E7D32", zorder=5,
        bbox=dict(boxstyle="round,pad=0.2", fc="#C8E6C9", ec="#2E7D32", lw=1))
ax.text(1.0, 3.30, "BLOCK", ha="center", va="center", fontsize=9.5,
        fontweight="bold", color="#C62828", zorder=5,
        bbox=dict(boxstyle="round,pad=0.2", fc="#FFCDD2", ec="#C62828", lw=1))

# ========== Arrows ==========
# Inputs → Compile
arrow(1.8,  7.4,  3.0,  6.55)
arrow(5.4,  7.4,  4.5,  6.55)
arrow(8.4,  7.4,  5.5,  6.55, cs="arc3,rad=0.15")

# Compile → Skill IR
arrow(6.5, 5.9, 8.0, 5.9)

# Compile → Gate
arrow(4.0, 5.3, 4.0, 4.55)

# Gate → Execute  (pass)
arrow(4.0, 3.3, 4.0, 2.65)

# Gate → Block (left)
arrow(1.5, 3.6, 0.5, 3.6, color="#C62828", lw=1.5)
ax.text(0.15, 3.6, "Safety\nReport", ha="center", va="center",
        fontsize=8, color="#C62828", fontweight="bold")

# Execute → Verify
arrow(3.0, 1.4, 2.0, 0.95)

# Verify → Optimize (fail path)
arrow(3.7, 0.3, 4.2, 0.3, color=C_FB, lw=2.0)
ax.text(3.95, 0.55, "Fail", ha="center", va="center",
        fontsize=9, color=C_FB, fontweight="bold")

# Verify → Skill Bank (success path)
arrow(2.0, -0.3, 8.5, 0.3, color="#2E7D32", lw=1.5, cs="arc3,rad=-0.15")
ax.text(5.5, -0.50, "Success  -->  Write to Bank",
        ha="center", va="center", fontsize=8.5,
        color="#2E7D32", fontweight="bold")

# Optimize → Skill Bank
arrow(7.7, 0.3, 8.5, 0.3, color=C_FB, lw=1.8)

# Skill Bank → Skill IR (feedback loop on right)
arrow(10.0, 0.9, 10.0, 4.95, color=C_FB, lw=2.0)
ax.text(11.2, 2.9,
        "Optimization\nLoop\n"
        r"$S'=\Pi_{\mathcal{S}_k}(S+\Delta_\sigma)$",
        ha="center", va="center", fontsize=9, color=C_FB, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", fc="#FFF3E0", ec=C_FB, lw=1.2))

# ========== Phase legend (right side) ==========
legend_x = 12.5
phases = [
    (7.8, "Input",    C_INPUT),
    (5.8, "Compile",  C_COMPILE),
    (3.8, "Gate",     C_GATE),
    (2.0, "Execute",  C_EXEC),
    (0.1, "Verify &\nOptimize", C_VERIFY),
]
for py, pl, pc in phases:
    b = FancyBboxPatch((legend_x - 0.1, py - 0.25), 1.6, 0.5,
                       boxstyle="round,pad=0.1", facecolor=pc,
                       edgecolor=C_BORDER, lw=1, alpha=0.85, zorder=2)
    ax.add_patch(b)
    ax.text(legend_x + 0.7, py, pl, ha="center", va="center",
            fontsize=9, fontweight="bold", color="#37474F", zorder=3)

# ========== Dashed phase grouping ==========
# Compile-time
r1 = mpatches.FancyBboxPatch(
    (0.1, 4.85), 7.2, 3.9,
    boxstyle="round,pad=0.2", fill=False,
    edgecolor="#1565C0", lw=1.3, ls="--", zorder=1)
ax.add_patch(r1)
ax.text(0.4, 8.6, "Compile Phase  (LLM-Assisted)",
        fontsize=10, color="#1565C0", fontweight="bold")

# Runtime
r2 = mpatches.FancyBboxPatch(
    (0.1, -0.6), 7.8, 4.6,
    boxstyle="round,pad=0.2", fill=False,
    edgecolor="#C62828", lw=1.3, ls="--", zorder=1)
ax.add_patch(r2)
ax.text(0.4, 3.85, "Execution Phase  (Deterministic Pipeline)",
        fontsize=10, color="#C62828", fontweight="bold")

# ========== Save ==========
plt.tight_layout()
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "results", "figures")
for ext in ("pdf", "png"):
    p = os.path.join(out_dir, f"fig_framework_overview.{ext}")
    fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"Saved  {p}")
plt.close()
print("Done.")
