# CASE-0010 — SSRF toward cloud metadata endpoint

**Type:** CASE  
**Status:** DRAFT (methodology-derived, not production BB)  
**Domain:** ssrf  
**Source:** SRC-methodology-ssrf  
**Security property:** ssrf

## Abstraction
Application fetches a user-supplied URL server-side; attacker points it at link-local cloud metadata.

## Observation
Unexpected internal response body markers (metadata JSON) without direct client access to that host.

## Not same as
- Intentional admin webhook to internal tools
- DNS rebinding without server-side fetch

## Related
PAT-0010 PROC-0010
