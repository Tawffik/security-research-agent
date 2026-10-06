# PROC-0021 — Cache deception baseline/challenge

**Type:** PROCEDURE  
**Domain:** cache  
**Status:** CURATED

## Steps
1. Map sensitive authenticated pages and cache headers.  
2. **baseline** — Direct authenticated access; record body markers.  
3. **challenge** — In-scope path manipulation aimed at static cache rules.  
4. **observe** — Second client without cookies retrieves markers.

## Required evidence
Two clients, same cache key, presence/absence of private fields, cache headers.
