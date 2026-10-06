# NEG-0004 — GraphQL introspection ≠ authorization bypass

**Type:** NEGATIVE  
**Domain:** authorization  
**Status:** CURATED

## Claim rejected
“Introspection enabled ⇒ broken object authorization.”

## Why insufficient
Introspection is a discovery surface. Authorization must be tested per operation
and object id with two identities (see PAT-0004, CASE-0007).

## Falsification of the false claim
Mutations/queries still enforce ownership when object ids are substituted.
