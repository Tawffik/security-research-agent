# NEG-0008 — Open redirect is not SSRF

**Type:** NEGATIVE  
**Domain:** ssrf  
**Status:** CURATED

## Claim rejected
“Location header points external ⇒ server-side request forgery.”

## Why
Browser navigates; server did not necessarily fetch the URL. Use PAT-0010 tests for SSRF.
