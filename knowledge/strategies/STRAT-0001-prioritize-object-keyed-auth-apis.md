# STRAT-0001 — Prioritize object-keyed authenticated APIs

**Type:** STRATEGY  
**Status:** DRAFT  
**Uses procedures:** PROC-0001, PROC-0002  

## Where to spend attention
Authenticated endpoints whose path/query/body includes object identifiers tied to user/tenant data (orders, docs, shops, vehicles, files).

## Why promising
High evidence potential for BOLA/IDOR; differential tests are cheap relative to info gain.

## What to test first
1. Cross-identity same object (PROC-0001)  
2. Same identity / substituted object key (PROC-0002)  

## What to skip early
- Pure static marketing pages  
- Hosts with only 404 park pages and no object API  
- Mass ID brute force before one discriminating pair  

## Abandon when
- Repeated denials with solid evidence of ownership checks  
- Objects proven public/shared by design  
- Budget/regret high with no belief change  

## Skill? No — strategy documentation only.
