# WRITEUP-SAMPLE-001 — Cross-tenant order ID access (fixture representing a real writeup)

**Source ID:** SRC-FX-0001  
**Origin:** offline fixture (not a live scrape)  
**Type:** writeup  
**Domain:** authorization  
**Security property:** authorization  

## Hypothesis
Object-level authorization fails when the server trusts a client-supplied order identifier without verifying ownership.

## Preconditions
- Two authenticated identities
- Order resource keyed by integer id
- Both identities in program scope

## Experiment
1. Baseline: owner retrieves order 1001
2. Challenge: non-owner requests the same id
3. Compare status and private fields

## Observation
Non-owner received HTTP 200 with the same private fields as the owner.

## Root cause
Authorization checked authentication presence, not resource ownership.

## Impact
Cross-identity read of private order data.

## False positives / not the same as
- Public catalog items intentionally shared
- Admin role with explicit elevated scope
- Cached CDN body for public pages

## Alternative explanations
- Mis-scoped lab identity
- Shared resource by design
