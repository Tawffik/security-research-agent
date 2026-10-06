# PAT-0023 — GraphQL batch or alias skips per-object authz

**Type:** PATTERN  
**Domain:** authorization  
**Status:** CURATED

## Abstraction
Batching features that authorize only the HTTP layer allow cross-object reads when resolvers assume a single parent authz decision.
