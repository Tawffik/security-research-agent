# TIP-0002 — SSRF: status alone is insufficient

**Type:** TIP / HEURISTIC  
**Domain:** ssrf  
**Security property:** ssrf  
**Tags:** tip, heuristic, ssrf  
**Status:** HEURISTIC

## Applicable context
Server-side URL fetch features under authorized testing.

## Signal
Response timing or body markers may matter more than status code alone.

## Experiment suggested
Baseline public URL vs controlled probe; compare body markers under policy.

## Negative evidence
Operator health-check endpoints intentionally internal.

## Limitations
Never expand to private network scanning; ScopeGuard first.

## Provenance
SRC-methodology-ssrf; offline curated tip
