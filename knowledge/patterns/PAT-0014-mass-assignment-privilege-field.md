# PAT-0014 — Mass assignment of privilege-bearing fields

**Type:** PATTERN  
**Domain:** authorization  
**Status:** CURATED

## Abstraction
When update endpoints bind entire request objects, client-controlled privilege fields
(`role`, `isAdmin`, `accountType`) can escalate authorization if the server lacks an allowlist.

## Not the same as
- Admin-only user management APIs with explicit role grants  
- Read-only role echoes in responses  
- Feature flags not used for authorization

## Discriminating experiment
1. Identify writable user/resource update  
2. Baseline: benign field change  
3. Challenge: inject privilege field  
4. Confirm privilege on a separate authorized action  

## Related
- CASE-0014  
- PROC-0014  
- PAT-0003 (mutation authz) — related but object-key vs field-bind
