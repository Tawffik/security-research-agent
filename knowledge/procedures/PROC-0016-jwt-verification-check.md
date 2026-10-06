# PROC-0016 — JWT verification discriminating check

**Type:** PROCEDURE  
**Domain:** authentication  
**Status:** CURATED

## Steps
1. **baseline** — Valid token on protected route.  
2. **challenge** — Bit-flip signature / empty signature.  
3. **compare** — Must deny.  
4. **optional** — Only under scope: known verification-confusion classes from methodology.

## Required evidence
- Status and body for baseline vs challenge  
- No claim from client-side JWT decode alone
