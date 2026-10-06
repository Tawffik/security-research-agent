# PAT-0035 — GraphQL Global ID without ownership bind

**Type:** PATTERN  
**Domain:** authorization  
**Status:** CURATED

## Abstraction
Relay Global IDs expose stable object references; resolvers that only decode and fetch skip per-viewer authorization. Common in real bounty disclosures.

## Not the same as
- Introspection enabled (NEG-0004)  
- GraphQL present without node interface
