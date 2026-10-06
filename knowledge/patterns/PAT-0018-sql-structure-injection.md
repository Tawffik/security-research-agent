# PAT-0018 — Attacker input alters SQL structure

**Type:** PATTERN  
**Domain:** injection  
**Status:** CURATED

## Abstraction
When user input is concatenated into SQL, attackers can change query structure.
Evidence is **behavioral differential** or equivalent strong proof — not a keyword list.

## Not the same as
- Verbose SQL errors without controllable structure change (needs more proof)  
- NoSQL operator injection (related family, different syntax)

## Discriminating experiment
Paired baseline/challenge predicates; reproducible content or status differential under scope.
