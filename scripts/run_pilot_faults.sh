#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_BASE=(ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o ConnectTimeout=30 -J openstack@222.200.180.102 ubuntu@10.10.3.110)
PYTHON_BIN="/Users/cpf/Documents/科研/PaperMachine/.venv/bin/python"

MODE="${1:-paper}"

case "$MODE" in
  fast)
    CHAOS_DURATION="25s"
    OBSERVE_SLEEP="5"
    ;;
  paper)
    CHAOS_DURATION="90s"
    OBSERVE_SLEEP="15"
    ;;
  *)
    echo "Usage: $0 [fast|paper]" >&2
    exit 1
    ;;
esac

run_skill() {
  local skill_path="$1"
  local report_name="$2"
  cd "$ROOT_DIR"
  "$PYTHON_BIN" -m opsskill.cli run "$skill_path" configs/cluster.opsskill_exp.yaml --execute --report-out "results/${report_name}"
}

apply_fault() {
  local fault_manifest="$1"
  sed "s/__CHAOS_DURATION__/${CHAOS_DURATION}/g" "$ROOT_DIR/${fault_manifest}" | "${SSH_BASE[@]}" "kubectl apply -f -"
}

wait_fault_observable() {
  sleep "$OBSERVE_SLEEP"
  "${SSH_BASE[@]}" "kubectl -n opsskill-exp get pods,events | tail -n +1"
}

echo "[OpsSkill] Running pilot faults in '${MODE}' mode (duration=${CHAOS_DURATION}, observe_sleep=${OBSERVE_SLEEP}s)"

"$ROOT_DIR/scripts/setup_opsskill_experiment.sh"

apply_fault experiments/chaos/cpu_stress.yaml
wait_fault_observable
run_skill skills/detection/metric_anomaly_detection.yaml pilot_cpu_detection.json
run_skill skills/diagnosis/pod_deployment_state_diagnosis.yaml pilot_cpu_diagnosis.json
run_skill skills/recovery/hidden_recovery_verification.yaml pilot_cpu_hidden_verify.json || true
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete stresschaos demo-app-cpu-stress --ignore-not-found=true"

apply_fault experiments/chaos/memory_stress.yaml
wait_fault_observable
run_skill skills/detection/k8s_event_burst_detection.yaml pilot_memory_detection.json
run_skill skills/diagnosis/topk_root_cause_generation.yaml pilot_memory_rca.json
run_skill skills/recovery/deployment_rollout_restart.yaml pilot_memory_recovery.json || true
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete stresschaos demo-app-memory-stress --ignore-not-found=true"

apply_fault experiments/chaos/network_delay.yaml
wait_fault_observable
run_skill skills/detection/config_change_correlation.yaml pilot_network_detection.json
run_skill skills/recovery/hidden_recovery_verification.yaml pilot_network_hidden_verify.json || true
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete networkchaos demo-app-network-delay --ignore-not-found=true"

"${SSH_BASE[@]}" "kubectl -n opsskill-exp get deploy,pods,svc -o wide"
