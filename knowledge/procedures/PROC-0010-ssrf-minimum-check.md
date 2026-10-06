# PROC-0010 — Minimum SSRF discriminating check

**Type:** PROCEDURE  
**Domain:** ssrf  
**Status:** CURATED

## Preconditions
- ScopeGuard ALLOW for the feature action  
- Program policy permits SSRF-class testing on this asset  
- No authorization to scan arbitrary internal ranges

## Steps
1. **baseline** — Invoke feature with an in-scope, policy-allowed public URL; store response class and body hash.  
2. **challenge** — Substitute a single policy-approved probe (lab collaborator or explicitly allowed test host).  
3. **compare** — Diff status, timing band, body markers; look for *internal content* reflected to client.  
4. **observe** — Record whether fetch is blocked, generic-error, or content-leaking.

## Required evidence
- Pair of observations with same feature path  
- Scope decision artifacts  
- No claim from timing alone without policy-approved OOB

## Stop conditions
- Scope deny  
- Clear allowlist failure without leakage → likely not exploitable SSRF  
- Content leakage of internal markers → promote to verification with skeptic questions
