# CASE-0020 — Open redirect used as auth/chain helper

**Type:** CASE  
**Status:** CURATED (Tier B)  
**Domain:** authentication  
**Sources:** SRC-0019

## Security properties violated
1. Redirect targets after login/oauth must be allowlisted to first-party locations.  
2. Open redirect alone may be low severity; impact rises when chained to token delivery.

## Decisive experiments
1. Baseline redirect to first-party path.  
2. Challenge external scheme/host in redirect parameter.  
3. Observe Location header / meta refresh.

## Falsification
External targets rejected or normalized to allowlist.
