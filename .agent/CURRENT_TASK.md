# Current Task

**Campaign:** IN_PROGRESS  
**Focus:** Evidence-requirement decision impact (skills)

## Result
Skill evidence_requirements now attach to Experiment.required_evidence when enable_skills=True.
Normalized identity-pair tokens participate in alignment checks.

Benchmark (offline):
- Skills change required_evidence set (measurable)
- Skills do not flip incomplete→confirmed or secure→FP
- Curated knowledge remains the TP driver
- Skills alone leave hard authz incomplete/FN

Suite: 462 passed / 8 skipped

## Blocked
Gate 6B live; live browser UI
