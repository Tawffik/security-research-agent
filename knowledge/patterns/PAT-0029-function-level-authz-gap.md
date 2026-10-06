# PAT-0029 — Broken function-level authorization

**Type:** PATTERN  
**Domain:** authorization  
**Status:** CURATED  
**Related cases:** CASE-0029

## Abstraction
When endpoints that change system-wide or privileged state only verify “logged in”
and not “allowed to perform this function,” lower-privilege identities can invoke admin capabilities.

## Not the same as
- Object-level IDOR (PAT-0001/0002) — wrong *object*, same function  
- Mass assignment of role fields (PAT-0014) — privilege via data binding  
- Missing authentication entirely (unauthenticated admin)

## Discriminating experiment
Admin baseline success vs low-privilege identical request; require side-effect evidence.

## Related procedure
PROC-0029
