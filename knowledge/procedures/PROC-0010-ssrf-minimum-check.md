# PROC-0010 — Minimum SSRF discriminating check

**Type:** PROCEDURE  
**Domain:** ssrf  
**Security property:** ssrf  
**Tags:** ssrf, procedure

## Minimum experiment
1. Baseline: request feature with a public allowed URL if permitted by scope  
2. Challenge: substitute a non-routable probe host or documented lab collaborator URL only  
3. Compare server behavior, errors, timing, and body markers  

## Evidence required
- Scope ALLOW for the action  
- Baseline and challenge observations  
- No mass internal network scan  

## Stop when
- Scope blocks  
- Evidence sufficient for confirm or reject  
- Risk policy forbids further probes  
