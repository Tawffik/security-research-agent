# CASE-0014 — Mass assignment elevates role via client-controlled field

**Type:** CASE  
**Status:** EXTRACTED (Tier B — methodology composite)  
**Domain:** authorization  
**Sources:** SRC-0010 (OWASP mass assignment concepts), SRC-0002 (API authz class)

## Security properties violated
1. Role / privilege fields must not be writable by the subject they authorize.  
2. Server must bind authorization state to session, not to client-supplied profile JSON.

## Target model
- **Actor:** authenticated user  
- **Action:** PATCH/POST profile or registration  
- **Resource:** user object  
- **Object key:** self user id  
- **Forbidden fields:** `role`, `isAdmin`, `permissions[]`

## Decisive experiments
1. Baseline: update allowed field (display name) → 200, role unchanged.  
2. Challenge: same request adds `"role":"admin"` or `"isAdmin":true` → must ignore or 403.  
3. Verify server-side role on a privileged endpoint after challenge.

## Alternatives (non-vuln)
- Separate admin provisioning API intentionally allows role set by admins only.  
- Field accepted in schema but stripped before persistence (must prove strip).

## Root cause
Framework binds request body to model without allowlist; authorization attributes treated as data.

## Falsification
Privileged field is stripped or rejected and privileged endpoint still denies the user.
