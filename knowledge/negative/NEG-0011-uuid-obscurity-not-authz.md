# NEG-0011 — UUID format is not proof of secure authorization

**Type:** NEGATIVE  
**Domain:** authorization  
**Status:** CURATED

## Claim rejected
“IDs are UUIDs ⇒ not BOLA / no need to test cross-account access.”

## Why insufficient
Authorization is a server check, not identifier entropy. Test with two controlled accounts (CASE-0030).
