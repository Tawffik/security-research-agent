# CASE-0027 — Server-side template injection

**Type:** CASE  
**Status:** CURATED (Tier B — SSTI class; **no exploit catalog**)  
**Domain:** injection  
**Sources:** SRC-0026

## Security properties violated
1. User input must not be evaluated as a template expression.  
2. Evidence is differential evaluation (e.g., arithmetic in template syntax) under scope — not a list of engine payloads.

## Decisive experiments
1. **Baseline:** literal marker reflected.  
2. **Challenge:** minimal template expression that would evaluate only if parsed as template.  
3. Compare output.

## Root cause
Rendering user strings as templates.

## Falsification
Input always treated as data; expressions not evaluated.
