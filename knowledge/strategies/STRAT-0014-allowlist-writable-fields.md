# STRAT-0014 — Prefer allowlists on writable identity fields

**Type:** STRATEGY  
**Domain:** authorization  
**Status:** CURATED

## Guidance
When profile/update APIs exist, prioritize experiments that probe privilege-bearing
fields and server-side allowlists before deep object-id matrices.

## When to apply
Target context shows PATCH/PUT user or account resources with rich JSON bodies.

## Not a permission
This strategy ranks experiments; it does not authorize live execution.
