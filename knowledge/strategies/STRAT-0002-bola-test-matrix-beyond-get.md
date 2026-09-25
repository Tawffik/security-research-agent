# STRAT-0002 — BOLA test matrix beyond GET

**Type:** STRATEGY  
**Status:** DRAFT  
**Source driver:** APIsec 100+ BOLA report analysis (May 2026)

## Attention rule
When object-keyed authenticated APIs exist, rank **mutating** opportunities alongside read opportunities — do not stop after one successful/failed GET differential.

## Matrix cells (priority order)
1. Horizontal read (A vs B, GET) — PROC-0001/0002  
2. Horizontal mutate (B acts on A’s object) — PROC-0003  
3. Lifecycle states if present (archived/deactivated) — later  
4. Tenant isolation if multi-tenant — later  
5. Vertical object ownership if roles exist — later  

## Skip / de-prioritize
- Hosts with no object API (park pages, pure 404)  
- Tag-noise “IDOR” without object reference  
- Spray of sequential ids before one controlled pair works  

## Success metric for the agent
Useful experiments that change beliefs about **ownership on mutate**, not count of DELETE attempts.

## Skill? No.
