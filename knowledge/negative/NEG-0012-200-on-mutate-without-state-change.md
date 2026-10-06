# NEG-0012 — HTTP 200 on mutate without durable state change ≠ BOLA

**Type:** NEGATIVE  
**Domain:** authorization  
**Status:** CURATED

## Claim rejected
“Peer got 200 on DELETE/PATCH ⇒ action-level BOLA.”

## Why insufficient
Must show **durable state change** (or equivalent). Idempotent 200/no-op is not proof.
