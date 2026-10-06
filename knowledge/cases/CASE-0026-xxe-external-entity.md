# CASE-0026 — XML parser resolves external entities

**Type:** CASE  
**Status:** CURATED (Tier B — XXE class)  
**Domain:** injection  
**Sources:** SRC-0025

## Security properties violated
1. XML parsers handling untrusted documents must disable external entities/DTDs by default.  
2. Confirmation needs controlled differential (file/OOB) under scope — not “XML accepted.”

## Decisive experiments
1. **Baseline:** benign XML accepted.  
2. **Challenge:** entity declaration pointing to policy-approved probe.  
3. Observe expansion/leakage.

## Falsification
External entities disabled; challenge no effect.
