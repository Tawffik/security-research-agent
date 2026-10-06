# PROC-0017 — CSRF state-change check

**Type:** PROCEDURE  
**Domain:** authentication  
**Status:** CURATED

## Steps
1. Map unsafe method + session cookie.  
2. **baseline** — Legitimate request with full browser artifacts.  
3. **challenge** — Omit CSRF token / simulate cross-site form.  
4. **observe** — State change vs reject.

## Required evidence
Before/after resource state; request headers; token presence/absence.
