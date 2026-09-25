# CASE-0002 — IDOR via direct database object reference

**Type:** CASE  
**Status:** EXTRACTED (methodology-derived)  
**Source:** SRC-0001 PortSwigger Academy — IDOR  
**URL:** https://portswigger.net/web-security/access-control/idor  
**Tier:** B — Methodology (not a single bounty payout record)

## Security property
Only the authorized owner (or policy-permitted principal) may read a customer account record.

## Model
- **Actor:** authenticated user  
- **Action:** GET customer account  
- **Resource:** `/customer_account?customer_number={id}`  
- **Object:** customer record indexed by `customer_number`  
- **Condition (expected):** object.owner == actor (or equivalent server-side policy)

## Observed failure mode (as described in source)
Server uses client-supplied `customer_number` as direct record index without adequate authorization binding → horizontal access to other customers' records.

## Decisive experiment (minimum)
1. As User A, request own `customer_number` → baseline 200 + ownership markers  
2. As User B, request User A's `customer_number` → compare status and body  
3. Stop if B is denied with no sensitive fields; continue evidence only if B receives A's private fields

## Alternative explanations to rule out
- Intended support/admin role  
- Public directory data  
- Same household/shared account by design  

## Root cause (abstract)
Authorization decision trusts user-controlled object key without binding to session identity.

## Evidence requirements for a real engagement
- Both identities authenticated  
- Object identifier under test  
- Response comparison  
- Scope allow  
- No reliance on status code alone  

## Why researcher stops
Property confirmed or disproven with discriminating identity pair — not after blind ID enumeration.

## Skill?
**No.** Case only → feeds PAT / PROC.
