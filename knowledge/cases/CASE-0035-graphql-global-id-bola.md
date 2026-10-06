# CASE-0035 — GraphQL Global ID / node interface cross-identity access

**Type:** CASE  
**Status:** CURATED (Tier B — systematic Global ID exploitation in disclosures)  
**Domain:** authorization  
**Generalizable:** true  
**Sources:** SRC-0032, CASE-0007, PAT-0004

## Security property
object-level authorization on Relay-style `node(id:)` and typed queries

## Actors
- user_a, user_b

## Resource
Global ID encoding type + internal db id (base64, etc.)

## Observation pattern (when vulnerable)
B queries `node(id: globalId_of_A_object)` or typed field with A’s Global ID and receives private fields.

## Hypothesis
node_resolver_skips_ownership_after_id_decode

## Minimum experiment
1. As A: fetch own object; capture Global ID  
2. As B: `node(id: …)` or equivalent typed query  
3. Compare private fields; optional mutation with same id

## Evidence required
Both sessions, Global IDs, field-level diff

## Alternatives
- Public Node types by design  
- Field-level authz hides sensitive selections (must verify)

## Disproof
Node returns null/forbidden for foreign ids; no private selections

## Root cause
Decode Global ID → load entity without viewer ownership check

## Variants
- Batch `nodes(ids:)`  
- Aliased multi-node queries (CASE-0023)

## Skill promotion
No
