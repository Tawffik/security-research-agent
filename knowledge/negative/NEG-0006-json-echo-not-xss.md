# NEG-0006 — JSON string echo is not HTML XSS

**Type:** NEGATIVE  
**Domain:** xss  
**Status:** CURATED

## Claim rejected
“Parameter value returned in JSON ⇒ Cross-Site Scripting.”

## Why insufficient
JSON APIs are not HTML contexts unless a page sinks the value into `innerHTML` or similar
without encoding. Prove the **browser HTML sink**, not the API echo.
