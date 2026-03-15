"""Experiment orchestrator — runs all methods on all tasks with fault injection.

Usage:
    python -m opsskill.experiment_runner \\
        --cluster configs/cluster.opsskill_exp.yaml \\
        --tasks experiments/task_cards \\
        --mode fast \\
        --methods B1-direct B2-react B3-reflexion B4-template B5-opsskill \\
        --out results/formal_experiment.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .baselines import TaskCard, TrialResult, build_all_methods, run_hidden_checks
from .metrics import (
    compute_domain_breakdown,
    compute_method_summary,
    generate_ablation_latex,
    generate_baseline_latex,
    generate_domain_latex,
    print_summary_table,
)
from .remote import RemoteK8sRunner
from .skill_schema import ClusterConfig

# ---------------------------------------------------------------------------
# Fault injection helpers
# ---------------------------------------------------------------------------

_SSH_BASE = [
    "ssh",
    "-o", "StrictHostKeyChecking=no",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=4",
    "-o", "ConnectTimeout=30",
]


def _ssh_cmd(cluster: ClusterConfig) -> list[str]:
    return _SSH_BASE + ["-J", cluster.jump_host] + cluster.ssh_options + [cluster.target_host]


def apply_fault(cluster: ClusterConfig, manifest_path: str, duration: str) -> None:
    """Apply a Chaos Mesh manifest to the remote cluster."""
    project_root = Path(__file__).resolve().parent.parent
    manifest_file = project_root / manifest_path
    if not manifest_file.exists():
        print(f"  [WARN] Chaos manifest not found: {manifest_file}", file=sys.stderr)
        return
    content = manifest_file.read_text().replace("__CHAOS_DURATION__", duration)
    # Use Popen so stdin closes properly after writing
    ssh = _ssh_cmd(cluster)
    proc = subprocess.Popen(
        ssh + ["kubectl apply -f -"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(input=content, timeout=30)
    if proc.returncode != 0:
        print(f"  [WARN] Chaos apply returned {proc.returncode}: {stderr[:200]}", file=sys.stderr)
    else:
        print(f"  [CHAOS] Applied {manifest_path} (duration={duration})")


def cleanup_fault(cluster: ClusterConfig, kind: str, name: str, namespace: str = "opsskill-exp") -> None:
    """Remove a Chaos Mesh resource from the remote cluster."""
    ssh = _ssh_cmd(cluster)
    subprocess.run(
        ssh + [f"kubectl -n {namespace} delete {kind} {name} --ignore-not-found=true"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(f"  [CHAOS] Cleaned up {kind}/{name}")


def wait_fault_observable(cluster: ClusterConfig, namespace: str, seconds: int) -> None:
    """Wait for fault effects to become observable."""
    print(f"  [WAIT] Sleeping {seconds}s for fault to propagate ...")
    time.sleep(seconds)
    ssh = _ssh_cmd(cluster)
    proc = subprocess.run(
        ssh + [f"kubectl -n {namespace} get pods,events 2>/dev/null | tail -15"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.stdout.strip():
        for line in proc.stdout.strip().split("\n")[:8]:
            print(f"    {line}")


# ---------------------------------------------------------------------------
# Fault domain configuration
# ---------------------------------------------------------------------------

FAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "cpu": {
        "manifest": "experiments/chaos/cpu_stress.yaml",
        "kind": "stresschaos",
        "name": "demo-app-cpu-stress",
    },
    "memory": {
        "manifest": "experiments/chaos/memory_stress.yaml",
        "kind": "stresschaos",
        "name": "demo-app-memory-stress",
    },
    "network": {
        "manifest": "experiments/chaos/network_delay.yaml",
        "kind": "networkchaos",
        "name": "demo-app-network-delay",
    },
}

DURATION_MAP = {"fast": "25s", "paper": "90s"}
OBSERVE_MAP = {"fast": 5, "paper": 15}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class ExperimentOrchestrator:
    """Run all methods across all task cards with fault injection."""

    def __init__(
        self,
        cluster_config_path: str | Path,
        tasks_dir: str | Path,
        mode: str = "fast",
        method_names: list[str] | None = None,
        project_root: str | Path | None = None,
    ):
        self.cluster = ClusterConfig.from_file(cluster_config_path)
        self.runner = RemoteK8sRunner(self.cluster)
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
        self.tasks_dir = Path(tasks_dir)
        self.mode = mode
        self.duration = DURATION_MAP.get(mode, "25s")
        self.observe_wait = OBSERVE_MAP.get(mode, 5)

        all_methods = build_all_methods(self.cluster, self.project_root)
        if method_names:
            self.methods = {k: v for k, v in all_methods.items() if k in method_names}
        else:
            self.methods = all_methods

    def load_task_cards(self) -> list[TaskCard]:
        """Load all task cards from the tasks directory."""
        cards: list[TaskCard] = []
        for path in sorted(self.tasks_dir.glob("*.yaml")):
            cards.append(TaskCard.from_file(path))
        if not cards:
            print(f"[ERROR] No task cards found in {self.tasks_dir}", file=sys.stderr)
        return cards

    def run_all(self) -> list[TrialResult]:
        """Execute the full experiment: for each fault domain, inject fault then run methods."""
        cards = self.load_task_cards()

        # Group task cards by fault domain
        by_domain: dict[str, list[TaskCard]] = {}
        for card in cards:
            by_domain.setdefault(card.fault_domain, []).append(card)

        all_results: list[TrialResult] = []

        for domain, domain_cards in sorted(by_domain.items()):
            fault_cfg = FAULT_CONFIGS.get(domain)
            if not fault_cfg:
                print(f"[WARN] No fault config for domain '{domain}', skipping", file=sys.stderr)
                continue

            print(f"\n{'='*60}")
            print(f"  FAULT DOMAIN: {domain.upper()} ({len(domain_cards)} tasks)")
            print(f"{'='*60}")

            # Separate read-only vs mutating tasks
            readonly_cards = [c for c in domain_cards if c.task_type == "read-only"]
            mutating_cards = [c for c in domain_cards if c.task_type != "read-only"]

            # --- Read-only tasks: single fault injection window for all methods ---
            if readonly_cards:
                print(f"\n  [ROUND] Read-only tasks ({len(readonly_cards)} tasks × {len(self.methods)} methods)")
                apply_fault(self.cluster, fault_cfg["manifest"], self.duration)
                wait_fault_observable(self.cluster, self.cluster.namespace, self.observe_wait)

                for card in readonly_cards:
                    for method_name, method in self.methods.items():
                        print(f"    [{method_name}] {card.name} ...", end=" ", flush=True)
                        try:
                            result = method.execute(card, self.runner)
                            all_results.append(result)
                            status = "✓" if result.task_success else "✗"
                            hv = "HV✓" if result.hidden_pass else "HV✗"
                            print(f"{status} {hv} score={result.score:.2f} ({result.wall_time:.1f}s)")
                        except Exception as exc:
                            print(f"ERROR: {exc}")
                            all_results.append(_error_result(method_name, card, str(exc)))

                cleanup_fault(self.cluster, fault_cfg["kind"], fault_cfg["name"], self.cluster.namespace)
                time.sleep(3)  # brief cooldown

            # --- Mutating tasks: separate fault injection per method ---
            for card in mutating_cards:
                print(f"\n  [ROUND] Mutating task: {card.name}")
                for method_name, method in self.methods.items():
                    apply_fault(self.cluster, fault_cfg["manifest"], self.duration)
                    wait_fault_observable(self.cluster, self.cluster.namespace, self.observe_wait)

                    print(f"    [{method_name}] {card.name} ...", end=" ", flush=True)
                    try:
                        result = method.execute(card, self.runner)
                        all_results.append(result)
                        status = "✓" if result.task_success else "✗"
                        hv = "HV✓" if result.hidden_pass else "HV✗"
                        print(f"{status} {hv} score={result.score:.2f} ({result.wall_time:.1f}s)")
                    except Exception as exc:
                        print(f"ERROR: {exc}")
                        all_results.append(_error_result(method_name, card, str(exc)))

                    cleanup_fault(self.cluster, fault_cfg["kind"], fault_cfg["name"], self.cluster.namespace)
                    time.sleep(5)  # wait for cluster to stabilise between methods

        return all_results

    def run_readonly_only(self) -> list[TrialResult]:
        """Run only read-only tasks (safe, no mutation) for quick validation."""
        cards = self.load_task_cards()
        readonly = [c for c in cards if c.task_type == "read-only"]

        by_domain: dict[str, list[TaskCard]] = {}
        for card in readonly:
            by_domain.setdefault(card.fault_domain, []).append(card)

        results: list[TrialResult] = []
        for domain, domain_cards in sorted(by_domain.items()):
            fault_cfg = FAULT_CONFIGS.get(domain)
            if not fault_cfg:
                continue

            print(f"\n  [DOMAIN] {domain.upper()} — {len(domain_cards)} read-only tasks")
            apply_fault(self.cluster, fault_cfg["manifest"], self.duration)
            wait_fault_observable(self.cluster, self.cluster.namespace, self.observe_wait)

            for card in domain_cards:
                for method_name, method in self.methods.items():
                    print(f"    [{method_name}] {card.name} ...", end=" ", flush=True)
                    try:
                        result = method.execute(card, self.runner)
                        results.append(result)
                        status = "✓" if result.task_success else "✗"
                        print(f"{status} score={result.score:.2f} ({result.wall_time:.1f}s)")
                    except Exception as exc:
                        print(f"ERROR: {exc}")
                        results.append(_error_result(method_name, card, str(exc)))

            cleanup_fault(self.cluster, fault_cfg["kind"], fault_cfg["name"], self.cluster.namespace)
            time.sleep(3)
        return results


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


# ---------------------------------------------------------------------------
# Results I/O
# ---------------------------------------------------------------------------


def save_results(results: list[TrialResult], path: str | Path) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        json.dump([asdict(r) for r in results], fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\n  [SAVED] {len(results)} trial results → {dest}")


def load_results(path: str | Path) -> list[TrialResult]:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        TrialResult(**{k: v for k, v in item.items()})
        for item in raw
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="OpsSkill formal experiment runner")
    parser.add_argument("--cluster", required=True, help="Path to cluster config YAML")
    parser.add_argument("--tasks", required=True, help="Directory of task card YAMLs")
    parser.add_argument("--mode", choices=["fast", "paper"], default="fast")
    parser.add_argument("--methods", nargs="*", help="Method names to run (default: all)")
    parser.add_argument("--readonly", action="store_true", help="Run only read-only tasks (safe)")
    parser.add_argument("--out", default="results/formal_experiment.json", help="Output file")
    parser.add_argument("--latex", default="results/tables", help="Directory for LaTeX tables")
    args = parser.parse_args()

    print(f"[OpsSkill Experiment] mode={args.mode}, methods={args.methods or 'all'}")
    print(f"  cluster: {args.cluster}")
    print(f"  tasks:   {args.tasks}")
    print(f"  output:  {args.out}")

    orch = ExperimentOrchestrator(
        cluster_config_path=args.cluster,
        tasks_dir=args.tasks,
        mode=args.mode,
        method_names=args.methods,
    )

    if args.readonly:
        results = orch.run_readonly_only()
    else:
        results = orch.run_all()

    # Save raw results
    save_results(results, args.out)

    # Compute and display summary
    print(f"\n{'='*60}")
    print("  EXPERIMENT SUMMARY")
    print(f"{'='*60}\n")

    summaries = compute_method_summary(results)
    print_summary_table(summaries)

    # Generate LaTeX tables
    latex_dir = Path(args.latex)
    latex_dir.mkdir(parents=True, exist_ok=True)

    baseline_tex = generate_baseline_latex(summaries)
    (latex_dir / "baseline_comparison.tex").write_text(baseline_tex, encoding="utf-8")

    ablation_tex = generate_ablation_latex(summaries)
    (latex_dir / "ablation_study.tex").write_text(ablation_tex, encoding="utf-8")

    domain_sums = compute_domain_breakdown(results)
    domain_tex = generate_domain_latex(domain_sums)
    (latex_dir / "domain_breakdown.tex").write_text(domain_tex, encoding="utf-8")

    print(f"\n  [LATEX] Tables written to {latex_dir}/")
    print("  Done.")


if __name__ == "__main__":
    main()
