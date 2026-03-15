# OpsSkill Skill Bank

This folder stores runnable or template-ready skill cards aligned with the current OpsSkill schema.

## Stage layout

- `detection/`: observation and task-card generation skills
- `diagnosis/`: diagnosis and root-cause summarization skills
- `recovery/`: mutating recovery and hidden verification skills

## Initial 12-skill set

### Detection
- `detection/metric_anomaly_detection.yaml`
- `detection/k8s_event_burst_detection.yaml`
- `detection/config_change_correlation.yaml`
- `detection/task_card_generation.yaml`

### Diagnosis
- `diagnosis/pod_deployment_state_diagnosis.yaml`
- `diagnosis/topk_root_cause_generation.yaml`
- `diagnosis/resource_bottleneck_localization.yaml`
- `diagnosis/root_cause_card_generation.yaml`

### Recovery
- `recovery/deployment_rollout_restart.yaml`
- `recovery/config_rollback.yaml`
- `recovery/patch_image_or_config.yaml`
- `recovery/hidden_recovery_verification.yaml`

## Notes

- Detection and diagnosis skills are mostly read-only and safe to use for evidence collection.
- Recovery skills should be run only after adapting targets such as deployment names or patch payloads.
- `patch_image_or_config.yaml` intentionally contains `PLACEHOLDER_IMAGE` and must be specialized before execution.
