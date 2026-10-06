# CASE-0030 — Opaque/UUIDs do not replace ownership checks

**Type:** CASE  
**Status:** CURATED (Tier A/B lesson from real BOLA programs)  
**Domain:** authorization  
**Generalizable:** true

## Security property
authorization / object ownership regardless of identifier entropy

## Actors
- user_a (owner of uuid-a)
- user_b (owner of uuid-b)

## Resource
object referenced by UUID/ULID/hash id

## Observation pattern (when vulnerable)
B requests `/api/objects/{uuid-a}` and receives A’s private representation.

## Hypothesis
security_team_assumed_unpredictable_ids_equal_authorization

## Experiment
Controlled pair of known UUIDs from two test accounts — not brute force.

## Evidence required
Both sessions, both object ids, private field differential

## Alternatives addressed
- “IDs are secret” is not an authorization control  
- Share links that mint capability tokens (different pattern if token binds access)

## Disproof
Cross-account UUID access denied without private fields

## Root cause
Identifier obscurity used as substitute for server-side ownership bind

## Linked
PAT-0001, PAT-0002, PROC-0001, NEG-0011
