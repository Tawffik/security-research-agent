# PROC-0018 — SQL injection boolean-pair discrimination

**Type:** PROCEDURE  
**Domain:** injection  
**Status:** CURATED

## Steps
1. Identify candidate sink (search, id, sort).  
2. **baseline** — Neutral value; hash result.  
3. **challenge-true / challenge-false** — Minimal paired probes under program policy.  
4. **compare** — Differential stability across repeats.

## Forbidden
- Dumping payload lists into trusted knowledge  
- Automated destructive queries

## Required evidence
Repeated pairs; notes on caching; scope allow.
