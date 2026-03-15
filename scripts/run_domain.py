#!/usr/bin/env python3
"""Run remaining experiment trials, one domain at a time.

Designed to be run repeatedly — safely skips already-completed trials.
Uses PYTHONUNBUFFERED=1 for immediate output.
"""

import json
import os
import sys
import time
from pathlib import Path

# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opsskill.baselines import TaskCard, TrialResult, build_all_methods, run_hidden_checks
from opsskill.experiment_runner import (
    DURATION_MAP, FAULT_CONFIGS, OBSERVE_MAP,
    apply_fault, cleanup_fault, save_results, wait_fault_observable,
)
from opsskill.remote import RemoteK8sRunner
from opsskill.skill_schema import ClusterConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLUSTER_CFG  = PROJECT_ROOT / "configs" / "cluster.opsskill_exp.yaml"
TASKS_DIR    = PROJECT_ROOT / "experiments" / "task_cards"
MODE         = "fast"
PARTIAL_FILE = PROJECT_ROOT / "results" / "formal_experiment.partial.json"

# Which domain to run — passed as argv[1]
DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "memory"


def _error_result(method, card, error):
    return TrialResult(
        method=method, task_name=card.name, fault_domain=card.fault_domain,
        task_family=card.task_family, task_success=False, hidden_pass=False,
        unsafe_actions=0, rollback_available=False, rollback_triggered=False,
        tool_calls=0, wall_time=0.0, precondition_checked=False,
        verification_formal=False, score=0.0, notes=f"ERROR: {error}",
    )


def load_partial():
    if PARTIAL_FILE.exists():
        with open(PARTIAL_FILE) as f:
            data = json.load(f)
        results = [TrialResult(**d) for d in data]
        keys = {(r.method, r.task_name) for r in results}
        return results, keys
    return [], set()


def save_partial(results):
    from dataclasses import asdict
    with open(PARTIAL_FILE, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"  [SAVED] {len(results)} results", flush=True)


def main():
    print(f"=== Running domain: {DOMAIN} ===", flush=True)

    cluster = ClusterConfig.from_file(CLUSTER_CFG)
    runner = RemoteK8sRunner(cluster)
    duration = DURATION_MAP[MODE]
    observe_wait = OBSERVE_MAP[MODE]

    # Load task cards for this domain
    cards = []
    for path in sorted(TASKS_DIR.glob("*.yaml")):
        c = TaskCard.from_file(path)
        if c.fault_domain == DOMAIN:
            cards.append(c)
    print(f"  Tasks: {[c.name for c in cards]}", flush=True)

    methods = build_all_methods(cluster, PROJECT_ROOT)
    all_results, completed = load_partial()
    print(f"  Partial: {len(all_results)} done, {len(completed)} keys", flush=True)

    fault_cfg = FAULT_CONFIGS[DOMAIN]

    # Read-only tasks
    readonly = [c for c in cards if c.task_type == "read-only"]
    mutating = [c for c in cards if c.task_type != "read-only"]

    if readonly:
        need_run = any(
            (m, c.name) not in completed
            for c in readonly for m in methods
        )
        if need_run:
            print(f"\n  [CHAOS] Injecting fault for read-only tasks...", flush=True)
            apply_fault(cluster, fault_cfg["manifest"], duration)
            wait_fault_observable(cluster, cluster.namespace, observe_wait)

            for card in readonly:
                for mname, method in methods.items():
                    if (mname, card.name) in completed:
                        print(f"    [{mname}] {card.name} ... SKIP", flush=True)
                        continue
                    print(f"    [{mname}] {card.name} ...", end=" ", flush=True)
                    try:
                        result = method.execute(card, runner)
                        all_results.append(result)
                        completed.add((mname, card.name))
                        s = "✓" if result.task_success else "✗"
                        h = "HV✓" if result.hidden_pass else "HV✗"
                        print(f"{s} {h} score={result.score:.2f} ({result.wall_time:.1f}s)", flush=True)
                    except Exception as e:
                        print(f"ERROR: {e}", flush=True)
                        all_results.append(_error_result(mname, card, str(e)))
                        completed.add((mname, card.name))
                    save_partial(all_results)

            cleanup_fault(cluster, fault_cfg["kind"], fault_cfg["name"], cluster.namespace)
            time.sleep(3)
        else:
            print(f"  [SKIP] All read-only tasks done", flush=True)

    # Mutating tasks
    for card in mutating:
        print(f"\n  [MUTATING] {card.name}", flush=True)
        for mname, method in methods.items():
            if (mname, card.name) in completed:
                print(f"    [{mname}] {card.name} ... SKIP", flush=True)
                continue
            print(f"    [CHAOS] Injecting for {mname}...", flush=True)
            apply_fault(cluster, fault_cfg["manifest"], duration)
            wait_fault_observable(cluster, cluster.namespace, observe_wait)

            print(f"    [{mname}] {card.name} ...", end=" ", flush=True)
            try:
                result = method.execute(card, runner)
                all_results.append(result)
                completed.add((mname, card.name))
                s = "✓" if result.task_success else "✗"
                h = "HV✓" if result.hidden_pass else "HV✗"
                print(f"{s} {h} score={result.score:.2f} ({result.wall_time:.1f}s)", flush=True)
            except Exception as e:
                print(f"ERROR: {e}", flush=True)
                all_results.append(_error_result(mname, card, str(e)))
                completed.add((mname, card.name))
            save_partial(all_results)

            cleanup_fault(cluster, fault_cfg["kind"], fault_cfg["name"], cluster.namespace)
            time.sleep(5)

    print(f"\n  ✅ Domain {DOMAIN} complete. Total: {len(all_results)} results", flush=True)


if __name__ == "__main__":
    main()
