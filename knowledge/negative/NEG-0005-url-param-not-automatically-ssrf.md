# NEG-0005 — URL query parameter ≠ SSRF

**Type:** NEGATIVE  
**Domain:** ssrf  
**Status:** CURATED

## Claim rejected
“Endpoint has `?url=` ⇒ server-side request forgery.”

## Why insufficient
- Parameter may be used only for client-side navigation or display.  
- Must show **server-side fetch** (egress, logs, collaborator, or internal content).  
- Open redirect is a different class (browser follows Location).

## Required instead
Baseline/challenge proving server-initiated request and policy bypass or internal leakage.
