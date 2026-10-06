# PAT-0025 — Secret links derived from request Host

**Type:** PATTERN  
**Domain:** authentication  
**Status:** CURATED

## Abstraction
Absolute URLs for resets/invites built from Host/`X-Forwarded-*` enable poisoning when those headers are attacker-controlled at the edge.
