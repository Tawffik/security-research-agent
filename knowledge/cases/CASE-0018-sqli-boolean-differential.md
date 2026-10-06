# CASE-0018 — SQL injection shown by boolean/content differential (methodology)

**Type:** CASE  
**Status:** CURATED (Tier B — PortSwigger SQLi class; **no payload catalog**)  
**Domain:** injection  
**Sources:** SRC-0017 (SQLi methodology)

## Security properties violated
1. Untrusted input must not change SQL parse structure.  
2. Confirmation requires **differential behavior** under controlled predicates — not error text alone.

## Target model
- **Actor:** attacker controlling a query parameter or body field  
- **Sink:** database-backed search/filter/login  
- **Control:** substring that could break out of quoted context

## Decisive experiments
1. **Baseline:** benign filter value; record result set size/hash.  
2. **Challenge:** paired requests that should be tautology vs contradiction **if** injected into SQL (academy-style minimal probes under scope).  
3. **Compare:** stable differential unexplained by application validation alone.  
4. **Skeptic:** WAF random errors, caching, pagination noise.

## Alternatives
- Input validated to enum/whitelist  
- ORM parameterized; differential absent

## Root cause
String concatenation into SQL instead of bind parameters.

## Falsification
No stable boolean differential; parameterized behavior under challenge.
