# CASE-0024 — OAuth redirect_uri not strictly validated

**Type:** CASE  
**Status:** CURATED (Tier B — OAuth security class)  
**Domain:** authentication  
**Sources:** SRC-0023

## Security properties violated
1. `redirect_uri` must match pre-registered exact values (or strict controlled patterns).  
2. Authorization codes/tokens must not be deliverable to attacker-controlled endpoints.

## Decisive experiments
1. **Baseline:** authorize with registered redirect — code lands on first-party.  
2. **Challenge:** subdomain/path/scheme tricks against registration policy.  
3. Observe where code/token is sent.

## Root cause
Prefix matching or open redirect in redirect_uri validation.

## Falsification
Only exact registered URIs accepted.
