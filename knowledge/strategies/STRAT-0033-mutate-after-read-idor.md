# STRAT-0033 — After read IDOR signal, test action-level on same object

**Type:** STRATEGY  
**Domain:** authorization  
**Status:** CURATED

## Guidance
Empirical ranking: read IDOR is common; **action-level** on the same object key often drives severity.
Sequence: PROC-0001 → if interesting → PROC-0033 → GraphQL node PROC-0035 if applicable.
Never skip ownership pair for UUID obscurity (NEG-0011).
