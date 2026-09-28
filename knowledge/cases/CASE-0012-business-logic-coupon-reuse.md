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
