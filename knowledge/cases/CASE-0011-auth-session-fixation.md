# CASE-0011 — Session fixation under authentication property

**Type:** CASE  
**Domain:** authentication  
**Security property:** authentication  
**Status:** DRAFT  

## Abstraction
Session identifier accepted before authentication remains valid after login without rotation.

## Not same as
- Intended long-lived API tokens with explicit binding

## Actors
- identity_a / identity_b (controlled pair)

## Evidence required
- Baseline and challenge observations under scope

## Disproof / falsification
Secure behavior: non-owner or unauthorized action denied without private side effects.

