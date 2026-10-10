# Current Task

**Campaign:** IN_PROGRESS  
**Focus:** Capability inventory + injection/XSS offline vertical slices

## Verified
- HEAD after inventory/labs (see git)
- Tests: 471 passed / 8 skipped
- Capability readiness matrix: `.agent/capability_readiness.json`
- hard_sqli / hard_xss labs + secure controls
- Methodology-aware polarity for xss/injection (no FP on encoded/parameterized)
- HARD_SCENARIOS extended

## Not done
- CSRF/JWT/path labs still knowledge-only or domain-parse gaps
- Gate 6B live authorization
- Held-out generalization for injection/XSS

## Blocked
- Gate 6B
