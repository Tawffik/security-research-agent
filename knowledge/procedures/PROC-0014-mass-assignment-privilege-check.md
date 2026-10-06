# PROC-0014 — Mass-assignment privilege field check

**Type:** PROCEDURE  
**Domain:** authorization  
**Status:** CURATED

## Steps
1. **baseline** — Authenticated update of an allowed field; record role/claims.  
2. **challenge** — Repeat with privilege-bearing field in body.  
3. **compare** — Re-read identity/role or call privileged endpoint.  
4. **observe** — Privilege must not change for non-admin actor.

## Required evidence
- Request/response pairs for baseline and challenge  
- Post-condition role or privileged-action outcome  
- Negative: field rejected/stripped → not a finding

## Stop conditions
- Privileged endpoint still denied after challenge  
- Field not accepted by schema (documented)
