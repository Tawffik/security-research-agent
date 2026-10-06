# CASE-0040 — Sensitive UI frameable (clickjacking class)

**Type:** CASE  
**Status:** CURATED (Tier B)  
**Domain:** ui_security  
**Generalizable:** true

## Security property
sensitive state-changing pages should not be embeddable cross-origin without framing controls

## Observation pattern (when vulnerable)
Missing CSP frame-ancestors / X-Frame-Options on sensitive flows

## Hypothesis
sensitive_flow_embeddable

## Minimum experiment
1. Identify sensitive UI (password change, confirm pay)  
2. Observe framing headers  
3. Lab iframe attempt under policy

## Evidence required
Headers + page class

## Disproof
DENY/SAMEORIGIN/CSP frame-ancestors blocks embedding

## Root cause
Missing anti-framing headers on sensitive routes
