# PROC-0035 — GraphQL Global ID cross-identity pair

**Type:** PROCEDURE  
**Domain:** authorization  
**Status:** CURATED

## Steps
1. As owner: obtain Global ID for private object  
2. As peer: node/typed query with that id  
3. Diff sensitive fields  
4. Optional: mutation with foreign Global ID (PROC-0033)

## Evidence required
Query documents, responses, identities
