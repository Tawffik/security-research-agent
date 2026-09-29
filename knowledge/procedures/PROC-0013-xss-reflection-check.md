# PROC-0013 — Minimum XSS reflection differential

**Type:** PROCEDURE  
**Domain:** xss  
**Security property:** xss  
**Tags:** xss, procedure  

## Minimum experiment
1. Baseline: unique benign token in parameter  
2. Challenge: encoding-sensitive characters in same parameter  
3. Compare reflection context and encoding in body  

## Evidence required
- Scope ALLOW  
- Observed reflection context  
- Encoding behavior  

## Preconditions
- Parameter-influenced response body  
- In-scope endpoint  

## Stop when
- No reflection  
- Encoding proven safe for context  
- CSP conclusively blocks (when measured)  
