#!/usr/bin/env python3
"""Generate LaTeX tables and print summary from experiment results."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opsskill.baselines import TrialResult
from opsskill.metrics import (
    compute_domain_breakdown,
    compute_method_summary,
    generate_ablation_latex,
    generate_baseline_latex,
    generate_domain_latex,
    print_summary_table,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = PROJECT_ROOT / "results" / "formal_experiment.json"
LATEX_DIR = PROJECT_ROOT / "results" / "tables"

def main():
    with open(RESULTS_FILE) as f:
        data = json.load(f)

    results = [TrialResult(**d) for d in data]
    print(f"Loaded {len(results)} results\n")

    summaries = compute_method_summary(results)
    print_summary_table(summaries)

    LATEX_DIR.mkdir(parents=True, exist_ok=True)

    baseline_tex = generate_baseline_latex(summaries)
    (LATEX_DIR / "baseline_comparison.tex").write_text(baseline_tex, encoding="utf-8")
    print(f"\n--- Baseline Table ---")
    print(baseline_tex)

    ablation_tex = generate_ablation_latex(summaries)
    (LATEX_DIR / "ablation_study.tex").write_text(ablation_tex, encoding="utf-8")
    print(f"\n--- Ablation Table ---")
    print(ablation_tex)

    domain_sums = compute_domain_breakdown(results)
    domain_tex = generate_domain_latex(domain_sums)
    (LATEX_DIR / "domain_breakdown.tex").write_text(domain_tex, encoding="utf-8")
    print(f"\n--- Domain Breakdown ---")
    print(domain_tex)

    print(f"\n✅ Tables written to {LATEX_DIR}/")


if __name__ == "__main__":
    main()
