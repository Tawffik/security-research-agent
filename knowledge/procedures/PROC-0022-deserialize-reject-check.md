# PROC-0022 — Deserialization reject/accept check

**Type:** PROCEDURE  
**Domain:** deserialization  
**Status:** CURATED

## Steps
1. Identify candidate cookie/body fields with binary/base64 object blobs.  
2. **baseline** — Valid session blob.  
3. **challenge** — Bit-flip / truncated / wrong-type blob.  
4. **observe** — Fail closed vs application error exposing deserializer stack.

## Forbidden
Publishing exploit gadget chains in trusted knowledge as payload catalogs.
