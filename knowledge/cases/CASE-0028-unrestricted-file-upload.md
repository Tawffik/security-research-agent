# CASE-0028 — Upload allows dangerous type or path

**Type:** CASE  
**Status:** CURATED (Tier B — file upload class)  
**Domain:** upload  
**Sources:** SRC-0027

## Security properties violated
1. Uploads must constrain type, size, and storage path; execution location must not be attacker-writable.  
2. Confirmation needs stored object proof + policy impact (e.g., reachable handler) under scope.

## Decisive experiments
1. **Baseline:** allowed image type stored as expected.  
2. **Challenge:** mismatched Content-Type/extension / path characters per methodology.  
3. Observe stored path and whether content is interpreted server-side.

## Falsification
Server normalizes type, stores outside exec root, serves with safe Content-Type.
