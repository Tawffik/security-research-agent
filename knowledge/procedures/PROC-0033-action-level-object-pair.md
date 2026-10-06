# PROC-0033 — Action-level object authorization pair

**Type:** PROCEDURE  
**Domain:** authorization  
**Status:** CURATED  
**Derived from:** CASE-0033, PAT-0033

## When to use
Recon shows object-keyed **mutating** methods; two identities available.

## Preconditions
- Scope allows method/host  
- Object creatable or enumerable under policy for test accounts  
- Observable durable state

## Hypothesis
Mutating handler skips object-level ownership check.

## Minimum experiment
1. Owner: capture object id + state  
2. Owner: action baseline  
3. Peer: identical action on same id  
4. Re-read state as owner

## Evidence required
Identities, pre/post state, status, scope decision

## Disproof
Peer denied; state unchanged

## Stop when
Evidence sufficient; equivalent action class already decided this episode
