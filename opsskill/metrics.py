"""Experiment metrics computation and LaTeX table generation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .baselines import TrialResult


@dataclass(slots=True)
class MethodSummary:
    """Aggregated metrics for one method across all tasks."""

    method: str
    n_tasks: int = 0
    task_success_rate: float = 0.0
    hidden_pass_rate: float = 0.0
    unsafe_action_rate: float = 0.0
    rollback_availability: float = 0.0
    rollback_trigger_rate: float = 0.0
    precondition_coverage: float = 0.0
    verification_coverage: float = 0.0
    avg_tool_calls: float = 0.0
    avg_wall_time: float = 0.0
    avg_score: float = 0.0


def compute_method_summary(results: list[TrialResult]) -> dict[str, MethodSummary]:
    """Group results by method and compute aggregated metrics."""
    by_method: dict[str, list[TrialResult]] = defaultdict(list)
    for r in results:
        by_method[r.method].append(r)

    summaries: dict[str, MethodSummary] = {}
    for method, trials in by_method.items():
        n = len(trials)
        summaries[method] = MethodSummary(
            method=method,
            n_tasks=n,
            task_success_rate=_ratio(trials, lambda t: t.task_success),
            hidden_pass_rate=_ratio(trials, lambda t: t.hidden_pass),
            unsafe_action_rate=sum(t.unsafe_actions for t in trials) / max(n, 1),
            rollback_availability=_ratio(trials, lambda t: t.rollback_available),
            rollback_trigger_rate=_ratio(trials, lambda t: t.rollback_triggered),
            precondition_coverage=_ratio(trials, lambda t: t.precondition_checked),
            verification_coverage=_ratio(trials, lambda t: t.verification_formal),
            avg_tool_calls=sum(t.tool_calls for t in trials) / max(n, 1),
            avg_wall_time=sum(t.wall_time for t in trials) / max(n, 1),
            avg_score=sum(t.score for t in trials) / max(n, 1),
        )
    return summaries


def compute_domain_breakdown(results: list[TrialResult]) -> dict[str, dict[str, MethodSummary]]:
    """Compute per-fault-domain summaries for each method."""
    by_domain: dict[str, list[TrialResult]] = defaultdict(list)
    for r in results:
        by_domain[r.fault_domain].append(r)
    return {domain: compute_method_summary(trials) for domain, trials in by_domain.items()}


# ---------------------------------------------------------------------------
# LaTeX table generation
# ---------------------------------------------------------------------------

_BASELINE_ORDER = ["B1-direct", "B2-react", "B3-reflexion", "B4-template", "B5-opsskill"]
_ABLATION_ORDER = ["A1-no-ir", "A2-no-hidden-verify", "A3-no-policy-gate", "B5-opsskill"]
_DISPLAY_NAMES = {
    "B1-direct": "Direct Cmd",
    "B2-react": "ReAct",
    "B3-reflexion": "Reflexion",
    "B4-template": "Template",
    "B5-opsskill": "\\textbf{OpsSkill}",
    "A1-no-ir": "w/o Typed IR",
    "A2-no-hidden-verify": "w/o Hidden Verif.",
    "A3-no-policy-gate": "w/o Policy Gate",
}


def generate_baseline_latex(summaries: dict[str, MethodSummary]) -> str:
    """Generate LaTeX table comparing baselines (Table 2 in paper)."""
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Baseline comparison across all fault domains.}",
        r"\label{tab:baseline-comparison}",
        r"\small",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"\textbf{Method} & \textbf{TSR}$\uparrow$ & \textbf{HVP}$\uparrow$ & \textbf{UAR}$\downarrow$ & \textbf{RA}$\uparrow$ & \textbf{TC}$\downarrow$ & \textbf{Score}$\uparrow$ \\",
        r"\midrule",
    ]

    for key in _BASELINE_ORDER:
        s = summaries.get(key)
        if s is None:
            continue
        display = _DISPLAY_NAMES.get(key, key)
        lines.append(
            f"{display} & {s.task_success_rate:.0%} & {s.hidden_pass_rate:.0%} & "
            f"{s.unsafe_action_rate:.2f} & {s.rollback_availability:.0%} & "
            f"{s.avg_tool_calls:.1f} & {s.avg_score:.0%} \\\\"
        )

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def generate_ablation_latex(summaries: dict[str, MethodSummary]) -> str:
    """Generate LaTeX table for ablation study (Table 3 in paper)."""
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Ablation study: contribution of each OpsSkill component.}",
        r"\label{tab:ablation}",
        r"\small",
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r"\textbf{Variant} & \textbf{TSR} & \textbf{HVP} & \textbf{UAR} & \textbf{Score} & $\Delta$\textbf{Score} \\",
        r"\midrule",
    ]

    full_score = summaries.get("B5-opsskill")
    base = full_score.avg_score if full_score else 0.0

    for key in _ABLATION_ORDER:
        s = summaries.get(key)
        if s is None:
            continue
        display = _DISPLAY_NAMES.get(key, key)
        delta = s.avg_score - base
        sign = "+" if delta >= 0 else ""
        lines.append(
            f"{display} & {s.task_success_rate:.0%} & {s.hidden_pass_rate:.0%} & "
            f"{s.unsafe_action_rate:.2f} & {s.avg_score:.0%} & {sign}{delta:.0%} \\\\"
        )

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def generate_domain_latex(domain_summaries: dict[str, dict[str, MethodSummary]]) -> str:
    """Generate per-domain breakdown table."""
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Per-domain hidden verification pass rate (HVP) and score by method.}",
        r"\label{tab:domain-breakdown}",
        r"\small",
    ]

    domains = sorted(domain_summaries.keys())
    ncols = 1 + 2 * len(domains)
    col_spec = "l" + "cc" * len(domains)
    lines.append(r"\begin{tabular}{" + col_spec + "}")
    lines.append(r"\toprule")

    header_parts = [r"\textbf{Method}"]
    for d in domains:
        header_parts.append(rf"\multicolumn{{2}}{{c}}{{\textbf{{{d.upper()}}}}}")
    lines.append(" & ".join(header_parts) + r" \\")

    sub_header = [""]
    for _ in domains:
        sub_header.extend(["HVP", "Score"])
    lines.append(" & ".join(sub_header) + r" \\")
    lines.append(r"\midrule")

    for key in _BASELINE_ORDER:
        display = _DISPLAY_NAMES.get(key, key)
        cells = [display]
        for d in domains:
            s = domain_summaries[d].get(key)
            if s:
                cells.extend([f"{s.hidden_pass_rate:.0%}", f"{s.avg_score:.0%}"])
            else:
                cells.extend(["--", "--"])
        lines.append(" & ".join(cells) + r" \\")

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    return "\n".join(lines)


def print_summary_table(summaries: dict[str, MethodSummary]) -> None:
    """Pretty-print a plaintext summary table to stdout."""
    header = f"{'Method':<22} {'TSR':>5} {'HVP':>5} {'UAR':>5} {'RA':>5} {'PC':>5} {'FV':>5} {'TC':>5} {'Time':>6} {'Score':>6}"
    print(header)
    print("-" * len(header))
    order = _BASELINE_ORDER + [k for k in _ABLATION_ORDER if k not in _BASELINE_ORDER]
    for key in order:
        s = summaries.get(key)
        if s is None:
            continue
        print(
            f"{key:<22} {s.task_success_rate:>5.0%} {s.hidden_pass_rate:>5.0%} "
            f"{s.unsafe_action_rate:>5.2f} {s.rollback_availability:>5.0%} "
            f"{s.precondition_coverage:>5.0%} {s.verification_coverage:>5.0%} "
            f"{s.avg_tool_calls:>5.1f} {s.avg_wall_time:>5.1f}s {s.avg_score:>6.0%}"
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _ratio(items: list, predicate) -> float:
    if not items:
        return 0.0
    return sum(1 for t in items if predicate(t)) / len(items)
