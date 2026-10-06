# PROC-0029 — Function-level authorization pair

**Type:** PROCEDURE  
**Domain:** authorization  
**Status:** CURATED  
**Derived from:** CASE-0029, PAT-0029

## When to use
Recon shows admin-like paths or privileged mutations; multiple roles exist.

## Preconditions
- Scope allows method/host  
- At least two roles (or capability sets) authorized for testing  
- Observable side effect or response marker for the action

## Hypothesis tested
Server does not enforce function permission beyond authentication.

## Minimum experiment
1. Privileged identity: perform action → markers  
2. Lower identity: same request → compare  
3. Prefer capability from recon, not full admin spidering

## Evidence required
Both identities, status, side effect or explicit denial, scope decision

## Disproof
Lower identity denied; no side effect

## Stop when
- Scope blocks  
- Evidence sufficient  
- Equivalent capability already tested this episode
