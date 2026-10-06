# PAT-0017 — Missing anti-CSRF action binding

**Type:** PATTERN  
**Domain:** authentication  
**Status:** CURATED

## Abstraction
State-changing endpoints authenticate the browser via cookies but do not bind the *intent*
with a CSRF token, SameSite policy, or equivalent.

## Not the same as
- CORS misconfiguration without cookie credentialed requests  
- XSS leading to same-site actions (different root cause)

## Discriminating experiment
Replay state change without anti-CSRF secret from cross-site context under lab policy.
