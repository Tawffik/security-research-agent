# CASE-0021 — Web cache deception exposes authenticated body

**Type:** CASE  
**Status:** CURATED (Tier B — cache deception class)  
**Domain:** cache  
**Sources:** SRC-0020 (web cache deception methodology)

## Security properties violated
1. Caches must not store personalized/authenticated responses under attacker-influenced cache keys that later serve other users.  
2. Path mapping and cache rules must agree on what is static vs dynamic.

## Target model
- **Actor:** attacker who can influence the request path (e.g. `/account/settings/..css`)  
- **Component:** shared HTTP cache (CDN/reverse proxy)  
- **Victim:** authenticated user who visits attacker link

## Decisive experiments
1. **Baseline:** authenticated request to sensitive path — note `Cache-Control` / body markers.  
2. **Challenge:** same session path shaped so cache treats it as static (methodology path tricks) while origin still returns private body.  
3. **Compare:** unauthenticated fetch of the *same cache key* returns victim body.  
4. **Skeptic:** was response actually public? Vary headers? cookie not part of key?

## Alternatives
- `Cache-Control: private` + uncacheable by design  
- Cache key includes authorization material

## Root cause
Mismatch between origin routing (dynamic) and cache hierarchy (static suffix rules).

## Falsification
Unauthenticated retrieval of the crafted key never contains private fields.
