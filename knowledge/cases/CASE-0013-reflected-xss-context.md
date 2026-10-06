# CASE-0013 — Reflected value in HTML context without contextual encoding

**Type:** CASE  
**Status:** CURATED (Tier B — PortSwigger XSS context class)  
**Domain:** xss  
**Sources:** SRC-0014 (PortSwigger XSS)

## Security properties violated
1. Untrusted input reflected into HTML must be encoded for **that context** (element body, attribute, JS string, URL).  
2. Finding requires executable or policy-relevant sink — not mere string presence.

## Target model
- **Actor:** attacker controlling a parameter (query/body/header as applicable)  
- **Action:** request that returns HTML  
- **Sink:** reflection point in response body  
- **Context:** must be classified (HTML text, attr, script, etc.)

## Decisive experiments
1. **Baseline:** unique benign marker reflected; note surrounding HTML.  
2. **Challenge:** context-appropriate breakout attempt **only as far as needed to test encoding** (lab/policy).  
3. **Compare:** whether output is encoded (`&lt;`) vs raw; CSP headers as confounders.  
4. **Skeptic:** is reflection in pure JSON? dead field? browser-not-executed path?

## Alternatives
- Encoding present → not XSS  
- CSP blocks inline execution → impact may be reduced (document; do not invent bypass)

## Root cause
Missing contextual encoding at the template/serializer boundary.

## Falsification
Marker only appears encoded; or never reaches HTML document context.
