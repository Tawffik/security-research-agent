# WRITEUP-SAMPLE-002 — Server-side fetch to link-local metadata (fixture)

**Source ID:** SRC-FX-0002  
**Origin:** offline fixture  
**Type:** writeup  
**Domain:** ssrf  
**Security property:** ssrf  

## Hypothesis
User-controlled URL is fetched server-side without blocking link-local addresses.

## Preconditions
- Fetch feature in scope
- Collaborator or lab probe permitted by policy

## Experiment
1. Baseline public URL
2. Challenge link-local probe URL only under authorization
3. Compare body markers

## Observation
Response body contained metadata-like markers for the challenge URL.

## Root cause
No allowlist; private/link-local ranges reachable.

## False positives / not the same as
- Intentional internal health checks by operators
- Open redirect without server-side fetch
