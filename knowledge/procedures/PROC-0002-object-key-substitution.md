# PROC-0002 — Object-key substitution under authorization

**Type:** PROCEDURE  
**Status:** DRAFT  
**From patterns:** PAT-0002  
**Cases:** CASE-0002, CASE-0004  

## When to use
Endpoint takes an object key and returns/mutates object data for an authenticated user.

## Preconditions
- Scope allows host/method  
- At least one legitimate object key for the actor  
- Preferably a second object key known not to belong to the actor (from listing or prior recon)

## Hypothesis
Server does not enforce object-level authorization on the key.

## Minimum experiment
1. Request with actor's own object key → baseline  
2. Substitute key to non-owned object → single request (not mass spray)  
3. Compare status + sensitive fields + ownership markers  

## Evidence
Both keys, both responses (or denial), identity, scope decision.

## Disproof
Consistent denial or non-sensitive public payload for non-owned keys.

## Stop when
- Scope/risk blocks  
- Evidence sufficient  
- Equivalent experiment cached  
- Listing-driven mass enumeration would only add redundant cost  

## Not a Skill yet
