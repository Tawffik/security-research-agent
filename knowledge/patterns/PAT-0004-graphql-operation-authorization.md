# PAT-0004 — GraphQL operation-level authorization gap

**Type:** PATTERN  
**Status:** DRAFT  
**Supported by:** CASE-0007 · HackerOne GraphQL authz discussion  

## Abstraction
Flexible schema (queries/mutations/field granularity) without per-operation and per-field authorization → authentication/authorization bypass or object access via alternate API channel.

## Signals
- `/graphql` endpoint  
- Introspection or schema leakage via errors/JS  
- Mutations: register, password, admin, delete, update by id  

## Experiments family
- Call sensitive mutation unauthenticated / as low-priv  
- Request nested fields that should be redacted  
- Object id arguments inside mutations (BOLA ∩ GraphQL)

## Not automatic finding
Introspection enabled alone is often accepted risk in BB programs — impact requires unauthorized operation success.

## Skill? No.
