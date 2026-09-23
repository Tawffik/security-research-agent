# PROC-0001 — Cross-Identity Object Access Check

**Type:** PROCEDURE (not a Skill)  
**Status:** DRAFT  
**Derived from:** CASE-0001, PAT-0001  
**Domain:** authorization

## When to use
Authenticated API exposes object identifiers and multiple identities exist.

## Preconditions
- Scope allows the host and method
- At least two authorized identities
- Object reference observable (path or parameter)

## Hypothesis tested
Server fails to bind object ownership to the acting identity.

## Minimum experiment
1. As owner: request object → record status + ownership markers  
2. As non-owner: same request → compare  
3. Prefer one differential pair — do not enumerate all IDs

## Evidence required
- Both identities
- Status codes
- Body markers or explicit denial
- Scope decision ALLOW

## Disproof
Non-owner consistently 403/404 with no sensitive fields; ownership markers only for owner.

## Stop when
- Scope blocks
- Evidence sufficient for confirm or reject
- Equivalent experiment already cached and still valid
- Information gain too low for further ID spray

## Not yet a Skill
Requires benchmark + baseline + review before any `skills/` promotion.
