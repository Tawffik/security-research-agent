# PAT-0022 — Native deserialization of untrusted input

**Type:** PATTERN  
**Domain:** deserialization  
**Status:** CURATED

## Abstraction
Passing untrusted bytes to language-native deserialization APIs enables object injection.

## Not the same as
- JSON.parse / safe schema decoding  
- HMAC-protected serialized blobs verified before deserialize
