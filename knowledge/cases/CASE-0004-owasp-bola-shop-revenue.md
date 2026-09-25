# CASE-0004 — BOLA on shop revenue API (OWASP scenario)

**Type:** CASE  
**Status:** EXTRACTED  
**Source:** SRC-0002 OWASP API1:2023 Broken Object Level Authorization  
**URL:** https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/  
**Tier:** B — Standards

## Security property
A shop operator may only access revenue data for shops they are authorized to manage.

## Model
- **Resource pattern:** `/shops/{shopName}/revenue_data.json`  
- **Object:** shop revenue dataset  
- **Attacker control:** `shopName` from listing of hosted shops  

## Failure mode
Endpoint authenticates the user but does not enforce object-level authorization on `shopName` → mass access to other shops' sales data.

## Discriminating experiment
1. List shops visible to attacker  
2. Request revenue for a shop not owned/managed by attacker  
3. Compare denial vs full revenue payload  

## Distinction (from source)
Access to the **function** may be allowed; the violation is **object-level** (BOLA not BFLA).

## Evidence requirements
- Attacker identity  
- Target shop object  
- Authorization expectation  
- Sensitive revenue fields in response  

## Skill? No.
