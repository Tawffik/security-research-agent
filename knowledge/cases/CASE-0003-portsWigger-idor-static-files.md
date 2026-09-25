# CASE-0003 — IDOR via static file object reference

**Type:** CASE  
**Status:** EXTRACTED (methodology-derived)  
**Source:** SRC-0001 PortSwigger Academy — IDOR  
**URL:** https://portswigger.net/web-security/access-control/idor  
**Tier:** B — Methodology

## Security property
Chat/transcript files belonging to one user must not be readable by another user by guessing storage names.

## Model
- **Action:** GET static transcript  
- **Resource:** `/static/{incrementing_id}.txt`  
- **Object:** transcript file  
- **Condition:** file owner == actor

## Failure mode
Predictable filesystem names + missing authz on static path → horizontal data exposure (credentials/PII risk).

## Minimum experiment
1. Obtain a legitimate transcript URL for identity A  
2. Request adjacent/other IDs as identity B  
3. Require content that is clearly another user's private data before claiming impact  

## Alternatives
- Deliberately public audit logs  
- Shared org workspace  

## Root cause
Static object reference without authorization middleware.

## Skill? No.
