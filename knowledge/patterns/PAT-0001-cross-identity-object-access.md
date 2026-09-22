# PAT-0001 — Cross-Identity Object Authorization Failure

**Type:** PATTERN  
**Domain:** authorization  
**Status:** DRAFT (documentation only — not an executable skill)

## Abstraction

When an API exposes object identifiers and multiple authenticated identities exist,
missing server-side ownership checks can allow identity B to read/modify identity A's object.

## Not the same as

- Intended shared resources
- Role-granted broader access
- Public endpoints

## Discriminating experiment (concept)

1. Identify object owned by A  
2. Replay request as B with same object id  
3. Compare status + body ownership markers  
4. Require evidence for ownership and both identities  

## Related procedure (future)

`procedures/PROC-cross-identity-object-access` — only after case support and benchmark.

## Skill promotion

Must not become `skills/*` until: cases + benchmark + differential evaluation + review.
