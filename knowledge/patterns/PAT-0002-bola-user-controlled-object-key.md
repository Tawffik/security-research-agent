# PAT-0002 — BOLA / user-controlled object key

**Type:** PATTERN  
**Status:** DRAFT  
**Supported by cases:** CASE-0002, CASE-0003, CASE-0004, CASE-0005, CASE-0001  

## Abstraction
Attacker is allowed to call the endpoint/function, but supplies an **object identifier** (id, name, VIN, filename) that the server uses to select a record **without** verifying the actor is authorized for that object.

## Preconditions (signals)
- Authenticated API or file endpoint  
- Object id in path, query, header, or body  
- Multiple tenants/users/objects exist  

## Not this pattern
- Broken **function** level authorization (admin-only endpoint reachable by user) → different pattern  
- Intentionally public objects  
- Shared ACL by design  

## Common root causes
- Missing ownership check  
- Comparing only session user id to a userId param (insufficient for many object types)  
- Static files outside auth middleware  

## Discriminating family of experiments
Cross-identity or cross-object request with **one** controlled key change; compare authorization outcome and sensitive fields.

## Linked procedure
PROC-0001 (cross-identity object access), PROC-0002 (object-key substitution under same identity listing)

## Skill promotion
Blocked until benchmark + baseline + review.
