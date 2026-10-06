# PAT-0034 — Vertical broken object authorization

**Type:** PATTERN  
**Domain:** authorization  
**Status:** CURATED

## Abstraction
Lower-privilege principals reach objects or representations intended for higher roles when routes omit role checks while still requiring login.

## Not the same as
- Horizontal peer IDOR (same role, wrong owner)  
- Broken function-level on pure admin *actions* without object key
