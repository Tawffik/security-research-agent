# CASE-0022 — Untrusted data reaches native deserializer

**Type:** CASE  
**Status:** CURATED (Tier B — insecure deserialization class)  
**Domain:** deserialization  
**Sources:** SRC-0021

## Security properties violated
1. Native serializers must not deserialize attacker-controlled blobs into executable object graphs.  
2. Confirmation needs proof of **gadget influence** or equivalent strong behavioral effect under scope — not mere “serialized-looking bytes.”

## Target model
- **Sink:** `ObjectInputStream`, `pickle.loads`, PHP `unserialize`, etc.  
- **Control:** cookie/body/file parameter  
- **Impact class:** RCE, auth bypass, or state corruption (program-dependent)

## Decisive experiments
1. **Baseline:** legitimate serialized value accepted.  
2. **Challenge:** structurally invalid / type-confused payload that should fail closed.  
3. **Optional:** in-scope lab gadget only when program allows RCE-class tests.  
4. **Skeptic:** is data only base64 JSON parsed safely?

## Root cause
Deserializer + attacker control + available gadgets / unsafe magic methods.

## Falsification
Input rejected before native deserialize; or safe allowlisted types only.
