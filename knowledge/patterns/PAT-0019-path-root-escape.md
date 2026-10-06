# PAT-0019 — Path root escape via user-controlled segments

**Type:** PATTERN  
**Domain:** traversal  
**Status:** CURATED

## Abstraction
File APIs that concatenate user path segments without resolving to a jailed root allow escape.

## Discriminating experiment
Baseline file vs traversal to in-scope marker; never exfiltrate unrelated customer data in production programs outside rules.
