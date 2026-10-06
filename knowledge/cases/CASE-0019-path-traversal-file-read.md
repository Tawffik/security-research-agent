# CASE-0019 — Path traversal reaches unintended file object

**Type:** CASE  
**Status:** CURATED (Tier B — PortSwigger directory traversal class)  
**Domain:** traversal  
**Sources:** SRC-0018

## Security properties violated
1. User-influenced file paths must stay within an allowed root.  
2. Confirmation requires reading a **non-intended** but policy-allowed probe file — not guessing secrets outside scope.

## Decisive experiments
1. **Baseline:** legitimate filename returns expected object.  
2. **Challenge:** traversal sequences under scope to a known lab marker file.  
3. Compare body to baseline; stop at scope boundary.

## Root cause
Path join without canonicalization/root jail.

## Falsification
Canonical path confined; traversal rejected.
