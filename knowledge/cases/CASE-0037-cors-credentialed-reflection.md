# CASE-0037 — CORS reflects attacker origin with credentials

**Type:** CASE  
**Status:** CURATED (Tier B)  
**Domain:** authentication  
**Generalizable:** true

## Security property
cross-origin credentialed reads must not reflect arbitrary Origin with ACAO + credentials

## Actors
- attacker origin  
- victim browser with cookies

## Observation pattern (when vulnerable)
`Access-Control-Allow-Origin: https://attacker` with `Allow-Credentials: true` on sensitive response

## Hypothesis
origin_reflection_with_credentials

## Minimum experiment
1. Baseline same-origin or allowlisted origin  
2. Challenge attacker Origin header  
3. Inspect ACAO/ACAC and body sensitivity

## Evidence required
Response headers + sensitive body sample

## Disproof
ACAO not attacker; or credentials false; or body non-sensitive

## Root cause
Reflect Origin without allowlist while enabling credentials
