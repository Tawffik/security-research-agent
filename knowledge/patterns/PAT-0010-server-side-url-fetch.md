# PAT-0010 — User input sinks into server-side URL fetch

**Type:** PATTERN  
**Domain:** ssrf  
**Status:** CURATED

## Abstraction
When application features cause the *server* to request a URL derived from user input,
attackers attempt to shift the request toward locations the client cannot reach directly
(metadata, internal admin, cloud IMDS). The security failure is **missing network-location policy**,
not “any URL parameter exists.”

## Not the same as
- Browser-only redirects (open redirect class — different pattern)  
- DNS rebinding without a server-side fetch  
- Intentional server calls to fixed first-party services

## Discriminating experiment
Baseline allowed URL vs challenge disallowed-class URL under **explicit scope**; compare leakage and errors — never mass-scan RFC1918.

## Evidence required
- Proof input controls fetch target  
- Baseline/challenge pair  
- Scope decision ALLOW for the action  

## Related
CASE-0010, PROC-0010, STRAT-0010, TIP-0002, NEG-0005
