# CASE-0025 — Password reset link poisoned via Host header

**Type:** CASE  
**Status:** CURATED (Tier B — host header injection class)  
**Domain:** authentication  
**Sources:** SRC-0024

## Security properties violated
1. Password-reset links must be built from a trusted configuration host, not the request Host header alone.  
2. Attacker must not receive the reset secret via a link they control.

## Decisive experiments
1. **Baseline:** reset email with normal Host — link points to real domain.  
2. **Challenge:** Host / `X-Forwarded-Host` manipulation under lab mail catcher.  
3. Compare link host in email body.

## Root cause
Using request host when generating absolute URLs for secrets.

## Falsification
Reset links always use configured canonical host.
