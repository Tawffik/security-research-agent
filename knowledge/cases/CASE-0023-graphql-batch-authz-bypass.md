# CASE-0023 — GraphQL batch/alias weakens object authorization

**Type:** CASE  
**Status:** CURATED (Tier B — GraphQL authz class)  
**Domain:** authorization  
**Sources:** SRC-0022 · related CASE-0007 PAT-0004

## Security properties violated
1. Each operation in a batch must enforce object-level authorization independently.  
2. Aliasing must not skip resolvers’ auth checks.

## Decisive experiments
1. **Baseline:** single query for object A as user A — success; as user B — deny.  
2. **Challenge:** batched/aliased queries requesting A’s object as B.  
3. Compare field presence per identity.

## Root cause
Authz applied once per HTTP request instead of per resolver/object.

## Falsification
Batch as B never returns A’s private fields.
