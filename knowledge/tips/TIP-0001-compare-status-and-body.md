# TIP-0001 — Compare status and body, not status alone

**Type:** TIP / HEURISTIC  
**Domain:** authorization  
**Security property:** authorization  
**Tags:** tip, heuristic, differential  
**Status:** HEURISTIC (not universal rule)

## Applicable context
Object-level authorization checks with multi-identity access.

## Signal
Identical HTTP status with different body privacy markers may indicate incomplete authorization.

## Hypothesis supported
Ownership check may be missing or partial.

## Experiment suggested
Baseline owner vs challenge non-owner; compare status AND private fields.

## Expected observation
Differential in body fields while status remains 200, or both change together.

## Negative evidence
Public resources or shared ACL objects that intentionally return the same body.

## Limitations
Tip is not proof of vulnerability; requires ownership expectation and scope.

## Provenance
SRC-methodology-differential; offline curated tip
