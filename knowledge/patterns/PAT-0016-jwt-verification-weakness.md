# PAT-0016 — Weak or confused JWT verification

**Type:** PATTERN  
**Domain:** authentication  
**Status:** CURATED

## Abstraction
APIs that decode JWTs without pinning algorithm/key allow forged claims. The pattern is
**verification failure**, not “JWT is used.”

## Not the same as
- Expired token still rejected correctly  
- Authorization bugs after valid authentication (those are BOLA/role patterns)

## Discriminating experiment
Valid vs invalid signature; optional in-scope alg/key confusion checks; never treat decode-without-verify as confirmed without evidence of acceptance.
