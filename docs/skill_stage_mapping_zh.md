# Skill Stage Mapping

## Detection
- observation skills dominate
- trigger output should be a normalized task card

## Diagnosis
- analysis skills dominate
- output should be a root-cause card with evidence and confidence

## Recovery
- action skills dominate
- every action skill should include preconditions, rollback, and hidden verification

## Important design rule

A detection skill should not directly mutate the cluster.
A diagnosis skill should almost always stay read-only.
A recovery skill is the only stage allowed to mutate environment state, and it must be policy-gated.
