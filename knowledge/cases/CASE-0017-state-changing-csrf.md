# CASE-0017 — State-changing request without anti-CSRF binding

**Type:** CASE  
**Status:** CURATED (Tier B — PortSwigger CSRF class)  
**Domain:** authentication  
**Sources:** SRC-0016 (CSRF methodology)
**Note:** Domain tagged authentication/session; impacts authorization of *actions*.

## Security properties violated
1. Browser-mediated state changes must bind to a secret not sent automatically cross-site (token, SameSite, etc.).  
2. Cookie session alone is insufficient for unsafe methods without additional defense.

## Target model
- **Actor:** victim browser with session cookie  
- **Action:** POST/PUT/DELETE sensitive state  
- **Missing:** CSRF token / strict SameSite / custom header requirement

## Decisive experiments
1. **Baseline:** legitimate UI request includes anti-CSRF artifact.  
2. **Challenge:** cross-site form or fetch **without** that artifact (lab victim session).  
3. Observe whether state changes.

## Alternatives
- SameSite=Lax/Strict effectively blocks the exploit path in modern browsers (document).  
- Token validated correctly.

## Root cause
Relying on cookies for unsafe methods without anti-CSRF control.

## Falsification
Request without token is rejected; or browser policy prevents the cross-site send.
