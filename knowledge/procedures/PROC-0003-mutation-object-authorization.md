# PROC-0003 — Mutation / action-level object authorization check

**Type:** PROCEDURE  
**Status:** DRAFT  
**From:** PAT-0003 · APIsec BOLA-in-the-wild findings  

## When to use
Authenticated endpoint accepts object id and performs DELETE/PATCH/POST side effect (not only GET).

## Preconditions
- Scope allows method  
- Two identities with distinct owned objects  
- Ability to observe side effect (list, re-fetch, absence)

## Hypothesis
Server authorizes the **action type** but not **object ownership** on mutate.

## Minimum experiment
1. Baseline: A mutates A’s object → success expected  
2. Discriminator: B mutates A’s object (single request)  
3. Observe: object state change / deletion / transfer  
4. Optional: vertical — low role mutates admin-owned object  

## Evidence
- Identities A/B  
- Object ids  
- Request method + body key  
- Before/after observation of object state  
- Scope allow  

## Disproof
Consistent denial **and** no side effect on A’s object.

## Stop when
- Side effect proven or solidly denied  
- Risk policy blocks destructive methods without approval  
- Equivalent mutation already tested for this object class  

## Explicit non-goals
Mass delete across id space; treating HTTP 200 without state proof as finding.

## Skill? No.
