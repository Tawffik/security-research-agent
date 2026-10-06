# CASE-0036 — HTTP request smuggling (front-end/back-end desync)

**Type:** CASE  
**Status:** CURATED (Tier B — PortSwigger desync class)  
**Domain:** smuggling  
**Generalizable:** true

## Security property
front-end and back-end must agree on request framing (Content-Length vs Transfer-Encoding)

## Actors
- attacker (can send crafted HTTP to the edge)
- victim (shares connection/pool)

## Resource
shared proxy/app HTTP parsing boundary

## Observation pattern (when vulnerable)
Differential responses, poisoned keep-alive, or lab collaborator hit explainable only by desync — under program-allowed tests.

## Hypothesis
parser_disagreement_on_request_boundaries

## Minimum discriminating experiment
1. Baseline normal request pair through edge  
2. Challenge CL.TE / TE.CL style probes **only if program policy allows**  
3. Compare framing effects; never DoS production

## Evidence required
Paired traces, proxy vs origin behavior notes, scope allow

## Alternatives
- WAF normalizes and rejects  
- Single parser end-to-end

## Disproof
No stable desync under controlled probes

## Root cause
Inconsistent HTTP/1.1 framing between layers

## Skill promotion
No — no payload encyclopedia in trusted knowledge
