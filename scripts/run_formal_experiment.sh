#!/usr/bin/env bash
# run_formal_experiment.sh — Entry point for the OpsSkill formal experiment.
#
# Usage:
#   ./scripts/run_formal_experiment.sh fast          # quick dev run
#   ./scripts/run_formal_experiment.sh paper          # full paper-quality run
#   ./scripts/run_formal_experiment.sh fast readonly   # only read-only tasks
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="/Users/cpf/Documents/科研/PaperMachine/.venv/bin/python"
SSH_BASE=(ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o ConnectTimeout=30 -J openstack@222.200.180.102 ubuntu@10.10.3.110)

MODE="${1:-fast}"
READONLY_FLAG=""
[[ "${2:-}" == "readonly" ]] && READONLY_FLAG="--readonly"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT_FILE="results/formal_${MODE}_${TIMESTAMP}.json"
LATEX_DIR="results/tables_${TIMESTAMP}"

echo "============================================================"
echo "  OpsSkill Formal Experiment"
echo "  Mode:   ${MODE}"
echo "  Output: ${OUT_FILE}"
echo "  LaTeX:  ${LATEX_DIR}/"
echo "============================================================"

# 1. Ensure experiment namespace and demo-app are ready
echo "[SETUP] Verifying experiment environment ..."
"${SSH_BASE[@]}" "kubectl -n opsskill-exp get deploy demo-app -o wide" || {
    echo "[SETUP] Running experiment setup script ..."
    "$ROOT_DIR/scripts/setup_opsskill_experiment.sh"
}

# 2. Clean any lingering chaos resources
echo "[CLEANUP] Removing stale Chaos Mesh resources ..."
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete stresschaos --all --ignore-not-found=true 2>/dev/null; \
                  kubectl -n opsskill-exp delete networkchaos --all --ignore-not-found=true 2>/dev/null; \
                  echo 'Chaos resources cleaned'"

# 3. Run the experiment
echo ""
echo "[RUN] Starting experiment runner ..."
cd "$ROOT_DIR"
"$PYTHON_BIN" -m opsskill.experiment_runner \
    --cluster configs/cluster.opsskill_exp.yaml \
    --tasks experiments/task_cards \
    --mode "$MODE" \
    --out "$OUT_FILE" \
    --latex "$LATEX_DIR" \
    $READONLY_FLAG

# 4. Final cleanup
echo ""
echo "[CLEANUP] Final chaos resource cleanup ..."
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete stresschaos --all --ignore-not-found=true 2>/dev/null; \
                  kubectl -n opsskill-exp delete networkchaos --all --ignore-not-found=true 2>/dev/null; \
                  echo 'Done'"

echo ""
echo "============================================================"
echo "  Experiment complete!"
echo "  Results: ${OUT_FILE}"
echo "  LaTeX:   ${LATEX_DIR}/"
echo "============================================================"
