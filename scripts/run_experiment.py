#!/usr/bin/env python3
"""Run the full OpsSkill experiment — optimized version with env caching.

This script runs all 8 methods across all 8 task cards in 3 fault domains.
It injects real Chaos Mesh faults and collects results.
"""

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opsskill.baselines import (
    TaskCard,
    TrialResult,
    build_all_methods,
    run_hidden_checks,
)
from opsskill.experiment_runner import (
    DURATION_MAP,
    FAULT_CONFIGS,
    OBSERVE_MAP,
    apply_fault,
    cleanup_fault,
    save_results,
    wait_fault_observable,
)
from opsskill.metrics import (
    compute_domain_breakdown,
    compute_method_summary,
    generate_ablation_latex,
    generate_baseline_latex,
    generate_domain_latex,
    print_summary_table,
)
from opsskill.remote import RemoteK8sRunner
from opsskill.skill_schema import ClusterConfig

# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLUSTER_CFG  = PROJECT_ROOT / "configs" / "cluster.opsskill_exp.yaml"
TASKS_DIR    = PROJECT_ROOT / "experiments" / "task_cards"
MODE         = "fast"          # fast = 25s chaos / 5s observe
OUT_FILE     = PROJECT_ROOT / "results" / "formal_experiment.json"
LATEX_DIR    = PROJECT_ROOT / "results" / "tables"
# ---------------------------------------------------------------------------


def _error_result(method: str, card: TaskCard, error: str) -> TrialResult:
    return TrialResult(
        method=method,
        task_name=card.name,
        fault_domain=card.fault_domain,
        task_family=card.task_family,
        task_success=False,
        hidden_pass=False,
        unsafe_actions=0,
        rollback_available=False,
        rollback_triggered=False,
        tool_calls=0,
        wall_time=0.0,
        precondition_checked=False,
        verification_formal=False,
        score=0.0,
        notes=f"ERROR: {error}",
    )


def main():
    cluster = ClusterConfig.from_file(CLUSTER_CFG)
    runner = RemoteK8sRunner(cluster)
    duration = DURATION_MAP[MODE]
    observe_wait = OBSERVE_MAP[MODE]

    # Load task cards
    cards: list[TaskCard] = []
    for path in sorted(TASKS_DIR.glob("*.yaml")):
        cards.append(TaskCard.from_file(path))
    print(f"[EXP] Loaded {len(cards)} task cards from {TASKS_DIR}")
    for c in cards:
        print(f"  {c.name} ({c.fault_domain}, {c.task_type})")

    # Build methods
    methods = build_all_methods(cluster, PROJECT_ROOT)
    print(f"[EXP] {len(methods)} methods: {list(methods.keys())}")

    # Group by fault domain
    by_domain: dict[str, list[TaskCard]] = {}
    for card in cards:
        by_domain.setdefault(card.fault_domain, []).append(card)

    all_results: list[TrialResult] = []

    # Load any previously saved partial results to allow resume
    partial_file = OUT_FILE.with_suffix(".partial.json")
    completed_keys: set[tuple[str,str]] = set()
    if partial_file.exists():
        with open(partial_file) as f:
            partial_data = json.load(f)
        for item in partial_data:
            tr = TrialResult(**item)
            all_results.append(tr)
            completed_keys.add((tr.method, tr.task_name))
        print(f"[EXP] Resumed {len(all_results)} partial results from {partial_file}")

    def _save_partial():
        save_results(all_results, partial_file)

    for domain, domain_cards in sorted(by_domain.items()):
        fault_cfg = FAULT_CONFIGS.get(domain)
        if not fault_cfg:
            print(f"[WARN] No fault config for domain '{domain}', skipping")
            continue

        print(f"\n{'='*60}")
        print(f"  FAULT DOMAIN: {domain.upper()} ({len(domain_cards)} tasks)")
        print(f"{'='*60}")

        readonly_cards = [c for c in domain_cards if c.task_type == "read-only"]
        mutating_cards = [c for c in domain_cards if c.task_type != "read-only"]

        # --- Read-only tasks: inject fault once, run all methods ---
        if readonly_cards:
            # Check if all readonly tasks in this domain are already done
            all_readonly_done = all(
                (m, c.name) in completed_keys
                for c in readonly_cards for m in methods
            )
            if all_readonly_done:
                print(f"\n  [SKIP] All read-only tasks already completed for {domain}")
            else:
                print(f"\n  [ROUND] Read-only tasks ({len(readonly_cards)} × {len(methods)} methods)")
                apply_fault(cluster, fault_cfg["manifest"], duration)
                wait_fault_observable(cluster, cluster.namespace, observe_wait)

                for card in readonly_cards:
                    for method_name, method in methods.items():
                        if (method_name, card.name) in completed_keys:
                            print(f"    [{method_name}] {card.name} ... SKIP (already done)")
                            continue
                        print(f"    [{method_name}] {card.name} ...", end=" ", flush=True)
                        try:
                            result = method.execute(card, runner)
                            all_results.append(result)
                            completed_keys.add((method_name, card.name))
                            status = "✓" if result.task_success else "✗"
                            hv = "HV✓" if result.hidden_pass else "HV✗"
                            print(f"{status} {hv} score={result.score:.2f} ({result.wall_time:.1f}s)")
                        except Exception as exc:
                            print(f"ERROR: {exc}")
                            all_results.append(_error_result(method_name, card, str(exc)))
                            completed_keys.add((method_name, card.name))
                        _save_partial()

                cleanup_fault(cluster, fault_cfg["kind"], fault_cfg["name"], cluster.namespace)
                time.sleep(3)

        # --- Mutating tasks: inject fault per method ---
        for card in mutating_cards:
            print(f"\n  [ROUND] Mutating: {card.name}")
            for method_name, method in methods.items():
                if (method_name, card.name) in completed_keys:
                    print(f"    [{method_name}] {card.name} ... SKIP (already done)")
                    continue
                apply_fault(cluster, fault_cfg["manifest"], duration)
                wait_fault_observable(cluster, cluster.namespace, observe_wait)

                print(f"    [{method_name}] {card.name} ...", end=" ", flush=True)
                try:
                    result = method.execute(card, runner)
                    all_results.append(result)
                    completed_keys.add((method_name, card.name))
                    status = "✓" if result.task_success else "✗"
                    hv = "HV✓" if result.hidden_pass else "HV✗"
                    print(f"{status} {hv} score={result.score:.2f} ({result.wall_time:.1f}s)")
                except Exception as exc:
                    print(f"ERROR: {exc}")
                    all_results.append(_error_result(method_name, card, str(exc)))
                    completed_keys.add((method_name, card.name))
                _save_partial()

                cleanup_fault(cluster, fault_cfg["kind"], fault_cfg["name"], cluster.namespace)
                time.sleep(5)

    # --- Save results ---
    save_results(all_results, OUT_FILE)
    if partial_file.exists():
        partial_file.unlink()
        print(f"  [CLEANUP] Removed partial file {partial_file}")

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  EXPERIMENT SUMMARY")
    print(f"{'='*60}\n")

    summaries = compute_method_summary(all_results)
    print_summary_table(summaries)

    # --- LaTeX tables ---
    LATEX_DIR.mkdir(parents=True, exist_ok=True)
    baseline_tex = generate_baseline_latex(summaries)
    (LATEX_DIR / "baseline_comparison.tex").write_text(baseline_tex, encoding="utf-8")
    ablation_tex = generate_ablation_latex(summaries)
    (LATEX_DIR / "ablation_study.tex").write_text(ablation_tex, encoding="utf-8")
    domain_sums = compute_domain_breakdown(all_results)
    domain_tex = generate_domain_latex(domain_sums)
    (LATEX_DIR / "domain_breakdown.tex").write_text(domain_tex, encoding="utf-8")
    print(f"\n  [LATEX] Tables written to {LATEX_DIR}/")

    print("\n  ✅ Experiment complete.")


if __name__ == "__main__":
    main()
