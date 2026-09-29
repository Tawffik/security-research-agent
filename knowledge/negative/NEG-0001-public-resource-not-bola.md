# NEG-0001 — Public resource is not BOLA

**Type:** NEGATIVE / FP GUIDANCE  
**Domain:** authorization  
**Security property:** authorization  
**Tags:** negative, false_positive, public  

## Abstraction
HTTP 200 on a resource explicitly marked public or shared does not constitute object-level authorization failure.

## When this applies
- Public catalog endpoints
- Shared team notes with multi-owner ACL
- Marketing pages

## Not a finding
Cross-identity 200 alone is insufficient without private-field differential and ownership expectation.
