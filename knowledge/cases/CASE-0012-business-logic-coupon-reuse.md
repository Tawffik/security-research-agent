# CASE-0012 — Coupon / credit reuse under business logic

**Type:** CASE  
**Domain:** business_logic  
**Security property:** business_logic  
**Status:** DRAFT  

## Hypothesis
Server does not bind one-time benefit to order or account state.

## Observation
Same coupon accepted on sequential checkouts in methodology examples.

## Preconditions
- Authenticated user
- Coupon endpoint in scope

## Not same as
- Intended multi-use marketing codes

## Actors
- identity_a / identity_b (controlled pair)

## Evidence required
- Baseline and challenge observations under scope

## Disproof / falsification
Secure behavior: non-owner or unauthorized action denied without private side effects.

