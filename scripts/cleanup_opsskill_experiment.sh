#!/usr/bin/env bash
set -euo pipefail

SSH_BASE=(ssh -o StrictHostKeyChecking=no -J openstack@222.200.180.102 ubuntu@10.10.3.110)

"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete stresschaos demo-app-cpu-stress demo-app-memory-stress --ignore-not-found=true"
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete networkchaos demo-app-network-delay --ignore-not-found=true"
"${SSH_BASE[@]}" "kubectl -n opsskill-exp delete deploy/demo-app svc/demo-app --ignore-not-found=true"
