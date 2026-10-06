# PAT-0015 — Check-then-act race on stateful benefits

**Type:** PATTERN  
**Domain:** business_logic  
**Status:** CURATED

## Abstraction
Validating “coupon unused” then marking used in two steps without atomicity
allows concurrent requests to both pass the check.

## Not the same as
- Duplicate client retries that are idempotent server-side  
- Multi-use coupons by design

## Discriminating experiment
Parallel identical redeem; count successful ledger entries.

## Related
CASE-0015, PROC-0012, PAT-0012
