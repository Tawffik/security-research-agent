# CASE-0013 — Reflected output without encoding (methodology-derived)

**Type:** CASE  
**Domain:** xss  
**Security property:** xss  
**Status:** DRAFT  
**Source:** SRC-methodology-xss offline  

## Hypothesis
User-controlled parameter is reflected into HTML context without encoding.

## Preconditions
- Parameter reaches HTML response body
- No strict CSP blocking inline script (unknown until observed)

## Experiment
1. Baseline benign marker
2. Challenge encoded/special characters in same parameter
3. Observe reflection context and encoding

## Observation
Unknown until measured — mark reflection context explicitly.

## False positives
- Encoded output that only looks similar in text form
- JSON API responses consumed by safe clients

## Negative evidence
Safe encoding of angle brackets; CSP blocking execution
