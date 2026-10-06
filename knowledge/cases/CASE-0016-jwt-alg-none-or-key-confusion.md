# CASE-0016 — JWT accepted with weakened verification (alg confusion class)

**Type:** CASE  
**Status:** CURATED (Tier B — methodology; PortSwigger JWT attacks class)  
**Domain:** authentication  
**Sources:** SRC-0015 (JWT methodology)

## Security properties violated
1. Tokens must be verified with an expected algorithm and key material server-side.  
2. Attacker must not be able to forge identity by switching `alg` or using public key as HMAC secret.

## Target model
- **Actor:** attacker with a legitimately issued token or captured header structure  
- **Action:** present JWT to API  
- **Resource:** protected route  
- **Control:** header/payload/signature bytes

## Decisive experiments
1. **Baseline:** valid token → 200 on protected resource.  
2. **Challenge A:** token with invalid signature → must 401.  
3. **Challenge B:** methodology-specific weak verification probes **only if in scope** (e.g., alg manipulation classes taught in academies) — never blast production with speculative crypto DoS.  
4. Compare subject claims accepted vs rejected.

## Alternatives
- Gateway rejects malformed JWT before app  
- Correct signature required; alg locked server-side

## Root cause
Verification library misconfigured (algorithm not pinned; key confusion).

## Falsification
Any signature bit-flip or alg change yields consistent authentication failure.
