# STRAT-0003 — BOLA: controlled identity pair before ID spray

**Type:** STRATEGY  
**Domain:** authorization  
**Status:** CURATED  
**Notion alignment:** Access control first; quality over volume

## Guidance
1. Obtain two authorized identities and one owned object.  
2. Run PROC-0001 / PROC-0002 once.  
3. Only then consider limited variant paths (CASE-0001 variants).  
4. Never treat recon host lists as ownership evidence.  
5. UUID opacity is not a stop condition (NEG-0011).

## Not a permission
Ranks experiments only; ScopeGuard still gates execution.
