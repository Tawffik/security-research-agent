# CASE-0010 — Server-side fetch reaches cloud metadata

**Type:** CASE  
**Status:** CURATED (Tier B — methodology composite; PortSwigger SSRF + cloud metadata class)  
**Domain:** ssrf  
**Sources:** SRC-0012 (PortSwigger SSRF), SRC-0013 (cloud metadata class)

## Security properties violated
1. Server-side HTTP clients must not fetch attacker-controlled URLs toward link-local or metadata ranges.  
2. Responses from internal fetches must not be returned (or influence) to the attacker in full.

## Target model
- **Actor:** low-privileged or unauthenticated user (feature-dependent)  
- **Action:** “import URL”, webhook test, PDF render, link preview  
- **Resource:** server-side HTTP client  
- **Control:** full or partial URL / host parameter  
- **Forbidden targets:** link-local metadata endpoints, internal admin hosts (policy-defined)

## Decisive experiments (minimum discriminating)
1. **Baseline:** feature fetches an *in-scope public* URL allowed by program policy → record status, body length, headers.  
2. **Challenge:** same feature with a **lab-only** non-routable or collaborator URL that is still within *authorized test policy* (never blast internal ranges).  
3. **Compare:** timing, error class, and whether *internal body markers* appear in the client-visible response.  
4. **Stop** if ScopeGuard / program policy forbids the next hop.

## Alternatives (non-vuln)
- Feature is documented egress to a fixed allowlist of hosts.  
- Errors are generic; no internal body returned (may still be blind SSRF — needs out-of-band under authorization only).

## Root cause
User input flows into server-side request URL without network-location policy (deny link-local / private by default).

## Falsification
Allowlisted egress only; challenge to disallowed location fails closed with no internal content leakage.
