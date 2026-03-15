#!/usr/bin/env python3
"""Smoke test — run B1 + B5 on one task card to validate experiment infrastructure."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opsskill.baselines import build_all_methods, TaskCard, run_hidden_checks
from opsskill.skill_schema import ClusterConfig
from opsskill.remote import RemoteK8sRunner


def main():
    cluster = ClusterConfig.from_file("configs/cluster.opsskill_exp.yaml")
    runner = RemoteK8sRunner(cluster)
    card = TaskCard.from_file("experiments/task_cards/cpu_detect_anomaly.yaml")
    print(f"Task: {card.name}, type: {card.task_type}, domain: {card.fault_domain}")
    print(f"Hidden checks: {len(card.hidden_checks)}")

    methods = build_all_methods(cluster, ".")
    for name in ["B1-direct", "B4-template", "B5-opsskill"]:
        m = methods[name]
        print(f"\n--- Running {name} on {card.name} ---")
        try:
            r = m.execute(card, runner)
            print(f"  success={r.task_success}, hidden={r.hidden_pass}, "
                  f"score={r.score:.3f}, time={r.wall_time:.1f}s")
            print(f"  commands={len(r.commands)}, tool_calls={r.tool_calls}")
            print(f"  precond_checked={r.precondition_checked}, verif_formal={r.verification_formal}")
        except Exception as exc:
            print(f"  ERROR: {exc}")
            import traceback; traceback.print_exc()

    print("\n--- Smoke test complete ---")


if __name__ == "__main__":
    main()
