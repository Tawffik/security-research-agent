# CASE-0032 — Concurrent purchase overselles constrained inventory

**Type:** CASE  
**Status:** CURATED (Tier B — race/business logic; parallel to CASE-0015)  
**Domain:** business_logic  
**Generalizable:** true

## Security property
inventory / stock must not go negative under concurrency

## Actors
- buyer_1, buyer_2 (or parallel same user sessions)

## Resource
product with stock=1

## Observation pattern (when vulnerable)
Two successful checkouts both claim the last unit.

## Hypothesis
check_stock_then_decrement_not_atomic

## Experiment
Parallel purchase/checkout on last unit; count success vs stock ledger

## Evidence required
- Initial stock  
- Both transaction outcomes  
- Final stock / order rows  

## Alternatives
- Queue serializes stock  
- Unique constraint on allocation

## Disproof
Only one success; second fails with clear stock error

## Root cause
TOCTOU on stock without transactional lock/constraint

## Linked
PAT-0015, PROC-0012, CASE-0015
