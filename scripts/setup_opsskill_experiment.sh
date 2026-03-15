#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_BASE=(ssh -o StrictHostKeyChecking=no -J openstack@222.200.180.102 ubuntu@10.10.3.110)

"${SSH_BASE[@]}" "kubectl apply -f -" < "$ROOT_DIR/experiments/manifests/demo_app.yaml"
"${SSH_BASE[@]}" "kubectl -n opsskill-exp rollout status deployment/demo-app --timeout=180s"
"${SSH_BASE[@]}" "kubectl -n opsskill-exp get deploy,pods,svc -o wide"
