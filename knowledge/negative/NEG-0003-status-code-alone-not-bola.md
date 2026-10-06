# NEG-0003 — HTTP status alone is not BOLA evidence

**Type:** NEGATIVE  
**Domain:** authorization  
**Status:** CURATED

## Claim rejected
“Both users got HTTP 200 on `/orders/{id}` ⇒ BOLA.”

## Why insufficient
- 200 may return empty shell, public summary, or masked fields.  
- Must compare **body ownership markers**, not status only.  
- Shared/public resources intentionally return 200.

## Required instead
Baseline/challenge differential on private fields + identity binding proof.

## Related tips
TIP-0001 (compare status and body)
