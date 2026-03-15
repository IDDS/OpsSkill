#!/usr/bin/env python3
"""Generate publication-quality figures from experiment results.

Produces:
  1. Baseline comparison bar chart (TSR, HVP, Score)
  2. Ablation study grouped bar chart
  3. Per-domain radar chart
  4. Score heatmap (method × task)
  5. Safety analysis: unsafe actions + policy gate
  6. Wall-time comparison
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opsskill.baselines import TrialResult
from opsskill.metrics import (
    MethodSummary,
    compute_domain_breakdown,
    compute_method_summary,
)

# ---------------------------------------------------------------------------
# Style configuration
# ---------------------------------------------------------------------------

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

COLORS = {
    "B1-direct":          "#9e9e9e",
    "B2-react":           "#ffb74d",
    "B3-reflexion":       "#4fc3f7",
    "B4-template":        "#81c784",
    "B5-opsskill":        "#e53935",
    "A1-no-ir":           "#ce93d8",
    "A2-no-hidden-verify":"#ff8a65",
    "A3-no-policy-gate":  "#a1887f",
}

DISPLAY_NAMES = {
    "B1-direct":          "Direct Cmd",
    "B2-react":           "ReAct",
    "B3-reflexion":       "Reflexion",
    "B4-template":        "Template",
    "B5-opsskill":        "OpsSkill",
    "A1-no-ir":           "w/o IR",
    "A2-no-hidden-verify":"w/o HiddenV",
    "A3-no-policy-gate":  "w/o Gate",
}

BASELINE_ORDER = ["B1-direct", "B2-react", "B3-reflexion", "B4-template", "B5-opsskill"]
ABLATION_ORDER = ["B5-opsskill", "A1-no-ir", "A2-no-hidden-verify", "A3-no-policy-gate"]

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_results(path: str | Path) -> list[TrialResult]:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return [TrialResult(**item) for item in raw]


# ---------------------------------------------------------------------------
# Fig 1: Baseline comparison bar chart
# ---------------------------------------------------------------------------

def fig_baseline_comparison(summaries: dict[str, MethodSummary], out_dir: Path):
    methods = [m for m in BASELINE_ORDER if m in summaries]
    metrics = ["task_success_rate", "hidden_pass_rate", "avg_score"]
    labels = ["Task Success\nRate (TSR)", "Hidden Verif.\nPass (HVP)", "Overall\nScore"]

    x = np.arange(len(methods))
    width = 0.25
    fig, ax = plt.subplots(figsize=(7, 4))

    for i, (metric, label) in enumerate(zip(metrics, labels)):
        vals = [getattr(summaries[m], metric) for m in methods]
        bars = ax.bar(x + i * width, vals, width, label=label,
                      color=[COLORS[m] for m in methods], alpha=0.85 - 0.15 * i,
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{v:.0%}", ha="center", va="bottom", fontsize=7)

    ax.set_ylabel("Rate / Score")
    ax.set_title("Baseline Comparison: Key Metrics")
    ax.set_xticks(x + width)
    ax.set_xticklabels([DISPLAY_NAMES[m] for m in methods])
    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend(loc="upper left", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(out_dir / "fig_baseline_comparison.pdf")
    fig.savefig(out_dir / "fig_baseline_comparison.png")
    plt.close(fig)
    print(f"  ✓ fig_baseline_comparison")


# ---------------------------------------------------------------------------
# Fig 2: Ablation study grouped bar chart
# ---------------------------------------------------------------------------

def fig_ablation_study(summaries: dict[str, MethodSummary], out_dir: Path):
    methods = [m for m in ABLATION_ORDER if m in summaries]
    if not methods:
        print("  ⚠ No ablation methods found, skipping")
        return

    metrics = ["task_success_rate", "hidden_pass_rate", "avg_score"]
    labels = ["TSR", "HVP", "Score"]

    x = np.arange(len(methods))
    width = 0.22
    fig, ax = plt.subplots(figsize=(6, 4))

    for i, (metric, label) in enumerate(zip(metrics, labels)):
        vals = [getattr(summaries[m], metric) for m in methods]
        bars = ax.bar(x + i * width, vals, width, label=label,
                      color=[COLORS[m] for m in methods], alpha=0.90 - 0.15 * i,
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{v:.0%}", ha="center", va="bottom", fontsize=7)

    # Show delta score relative to full system
    if "B5-opsskill" in summaries:
        full_score = summaries["B5-opsskill"].avg_score
        for j, m in enumerate(methods):
            delta = summaries[m].avg_score - full_score
            if delta != 0:
                sign = "+" if delta >= 0 else ""
                ax.annotate(f"Δ={sign}{delta:.0%}",
                           xy=(j + 2*width, summaries[m].avg_score),
                           xytext=(0, 15), textcoords="offset points",
                           fontsize=7, ha="center", color="red",
                           arrowprops=dict(arrowstyle="->", color="red", lw=0.5))

    ax.set_ylabel("Rate / Score")
    ax.set_title("Ablation Study: Component Contribution")
    ax.set_xticks(x + width)
    ax.set_xticklabels([DISPLAY_NAMES[m] for m in methods])
    ax.set_ylim(0, 1.25)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend(loc="upper right", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(out_dir / "fig_ablation_study.pdf")
    fig.savefig(out_dir / "fig_ablation_study.png")
    plt.close(fig)
    print(f"  ✓ fig_ablation_study")


# ---------------------------------------------------------------------------
# Fig 3: Per-domain radar chart
# ---------------------------------------------------------------------------

def fig_domain_radar(summaries: dict[str, MethodSummary],
                     domain_sums: dict[str, dict[str, MethodSummary]],
                     out_dir: Path):
    domains = sorted(domain_sums.keys())
    methods = [m for m in BASELINE_ORDER if m in summaries]

    # For each method, compute per-domain score
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, len(domains), endpoint=False).tolist()
    angles += angles[:1]

    for method in methods:
        vals = []
        for d in domains:
            s = domain_sums[d].get(method)
            vals.append(s.avg_score if s else 0.0)
        vals += vals[:1]
        ax.plot(angles, vals, "o-", linewidth=1.5, label=DISPLAY_NAMES[method],
                color=COLORS[method], markersize=4)
        ax.fill(angles, vals, alpha=0.08, color=COLORS[method])

    ax.set_thetagrids([a * 180 / np.pi for a in angles[:-1]],
                       [d.upper() for d in domains])
    ax.set_ylim(0, 1.0)
    ax.set_title("Per-Domain Score Breakdown", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), framealpha=0.9)

    fig.savefig(out_dir / "fig_domain_radar.pdf")
    fig.savefig(out_dir / "fig_domain_radar.png")
    plt.close(fig)
    print(f"  ✓ fig_domain_radar")


# ---------------------------------------------------------------------------
# Fig 4: Score heatmap (method × task)
# ---------------------------------------------------------------------------

def fig_score_heatmap(results: list[TrialResult], out_dir: Path):
    methods = BASELINE_ORDER
    tasks = sorted(set(r.task_name for r in results))

    score_mat = np.full((len(methods), len(tasks)), np.nan)
    for r in results:
        if r.method in methods:
            mi = methods.index(r.method)
            ti = tasks.index(r.task_name)
            score_mat[mi, ti] = r.score

    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.imshow(score_mat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)

    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels([t.replace("-", "\n") for t in tasks], fontsize=7, rotation=30, ha="right")
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels([DISPLAY_NAMES[m] for m in methods])

    # Annotate cells
    for i in range(len(methods)):
        for j in range(len(tasks)):
            val = score_mat[i, j]
            if not np.isnan(val):
                txt = f"{val:.0%}"
                color = "white" if val < 0.4 or val > 0.85 else "black"
                ax.text(j, i, txt, ha="center", va="center", fontsize=7, color=color)

    ax.set_title("Score Heatmap: Method × Task")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Score")

    fig.savefig(out_dir / "fig_score_heatmap.pdf")
    fig.savefig(out_dir / "fig_score_heatmap.png")
    plt.close(fig)
    print(f"  ✓ fig_score_heatmap")


# ---------------------------------------------------------------------------
# Fig 5: Safety analysis — unsafe actions + HVP gap
# ---------------------------------------------------------------------------

def fig_safety_analysis(summaries: dict[str, MethodSummary], out_dir: Path):
    methods = [m for m in BASELINE_ORDER + ["A3-no-policy-gate"] if m in summaries]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # Left: unsafe action rate
    uar_vals = [summaries[m].unsafe_action_rate for m in methods]
    colors = [COLORS[m] for m in methods]
    bars = ax1.barh(range(len(methods)), uar_vals, color=colors, edgecolor="white")
    ax1.set_yticks(range(len(methods)))
    ax1.set_yticklabels([DISPLAY_NAMES[m] for m in methods])
    ax1.set_xlabel("Unsafe Action Rate (UAR)")
    ax1.set_title("Safety: Unsafe Actions")
    ax1.invert_yaxis()
    for bar, v in zip(bars, uar_vals):
        ax1.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{v:.2f}", va="center", fontsize=8)

    # Right: HVP gap = TSR - HVP (false positive gap)
    tsr_vals = [summaries[m].task_success_rate for m in methods]
    hvp_vals = [summaries[m].hidden_pass_rate for m in methods]
    gap_vals = [max(0, t - h) for t, h in zip(tsr_vals, hvp_vals)]

    y_pos = range(len(methods))
    ax2.barh(y_pos, hvp_vals, color=colors, edgecolor="white", label="HVP", alpha=0.8)
    ax2.barh(y_pos, gap_vals, left=hvp_vals, color="lightcoral", edgecolor="white",
             label="FP Gap", alpha=0.6, hatch="//")
    ax2.set_yticks(range(len(methods)))
    ax2.set_yticklabels([DISPLAY_NAMES[m] for m in methods])
    ax2.set_xlabel("Rate")
    ax2.set_title("Hidden Verification Gap (False Positives)")
    ax2.invert_yaxis()
    ax2.legend(loc="lower right", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_dir / "fig_safety_analysis.pdf")
    fig.savefig(out_dir / "fig_safety_analysis.png")
    plt.close(fig)
    print(f"  ✓ fig_safety_analysis")


# ---------------------------------------------------------------------------
# Fig 6: Wall-time comparison
# ---------------------------------------------------------------------------

def fig_wall_time(summaries: dict[str, MethodSummary], out_dir: Path):
    methods = [m for m in BASELINE_ORDER if m in summaries]

    times = [summaries[m].avg_wall_time for m in methods]
    scores = [summaries[m].avg_score for m in methods]

    fig, ax = plt.subplots(figsize=(6, 4))
    for m, t, s in zip(methods, times, scores):
        ax.scatter(t, s, s=120, c=COLORS[m], edgecolors="black", linewidths=0.5,
                   zorder=3, label=DISPLAY_NAMES[m])
        ax.annotate(DISPLAY_NAMES[m], (t, s), textcoords="offset points",
                   xytext=(5, 5), fontsize=8)

    ax.set_xlabel("Average Wall Time (s)")
    ax.set_ylabel("Average Score")
    ax.set_title("Efficiency: Score vs. Time")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.3)

    fig.savefig(out_dir / "fig_wall_time.pdf")
    fig.savefig(out_dir / "fig_wall_time.png")
    plt.close(fig)
    print(f"  ✓ fig_wall_time")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_all_figures(results_path: str | Path, out_dir: str | Path = "results/figures"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = load_results(results_path)
    print(f"[PLOT] Loaded {len(results)} trial results")

    summaries = compute_method_summary(results)
    domain_sums = compute_domain_breakdown(results)

    fig_baseline_comparison(summaries, out)
    fig_ablation_study(summaries, out)
    fig_domain_radar(summaries, domain_sums, out)
    fig_score_heatmap(results, out)
    fig_safety_analysis(summaries, out)
    fig_wall_time(summaries, out)

    print(f"\n  ✅ All figures saved to {out}/")


if __name__ == "__main__":
    results_file = sys.argv[1] if len(sys.argv) > 1 else "results/formal_experiment.json"
    generate_all_figures(results_file)
