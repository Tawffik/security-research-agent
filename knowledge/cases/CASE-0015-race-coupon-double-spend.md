# CASE-0015 — Race on single-use coupon (stateful benefit)

**Type:** CASE  
**Status:** EXTRACTED (Tier B — business logic)  
**Domain:** business_logic  
**Related:** CASE-0012, PAT-0012

## Security properties violated
1. Single-use benefits must be consumed at most once under concurrency.  
2. Check-then-act on coupon state without atomicity enables double spend.

## Decisive experiments
1. Issue single-use coupon bound to account.  
2. Parallel redeem requests (same coupon) before state flips.  
3. Observe whether two successful redemptions persist.

## Alternatives
- Idempotent redeem with single ledger row and unique constraint  
- Server-side lock / transactional consume

## Falsification
Database unique constraint or atomic consume allows only one success; second is rejected with clear state.
