# PAT-0033 — Action-level broken object authorization

**Type:** PATTERN  
**Domain:** authorization  
**Status:** CURATED  
**Related:** CASE-0033, PAT-0001 (read), PAT-0003 (mutation matrix)

## Abstraction
The caller is allowed the *kind* of action (cancel, edit, delete) but the server fails to verify that the target object is within the caller’s ownership/ACL. Empirical bug-bounty data shows this family is as central as pure read IDOR.

## Not the same as
- Function-level admin endpoint exposure (PAT-0029)  
- Mass assignment of role fields (PAT-0014)  
- Read-only cross-identity GET (PAT-0001) — related but weaker impact class

## Discriminating experiment
Owner baseline mutate → peer same action on same object key → require durable state proof.
