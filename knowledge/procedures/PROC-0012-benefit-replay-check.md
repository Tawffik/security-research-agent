# PROC-0012 — Minimum benefit replay check

**Type:** PROCEDURE  
**Domain:** business_logic  
**Security property:** business_logic  

## Minimum experiment
1. Baseline: redeem benefit once under authorized identity  
2. Challenge: replay same token/code once  
3. Compare acceptance vs rejection and ledger state  

## Evidence required
- Both outcomes observed  
- Scope ALLOW  
- No mass coupon spraying  
