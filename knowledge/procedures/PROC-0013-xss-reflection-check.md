# PROC-0013 — XSS reflection and context check

**Type:** PROCEDURE  
**Domain:** xss  
**Status:** CURATED

## Steps
1. **baseline** — Inject unique marker; locate reflection; photograph context (HTML/attr/script).  
2. **challenge** — Test whether special characters are encoded for that context.  
3. **compare** — Encoded vs raw; note CSP/COOP confounders.  
4. **observe** — Do not claim “XSS” from marker echo in JSON or logs alone.

## Required evidence
- Response snippet with context  
- Encoding behavior  
- Impact path (execution or credible HTML injection under policy)

## Stop when
- Fully encoded in safe context  
- No HTML document involved
