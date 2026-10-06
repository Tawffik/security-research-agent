# NEG-0010 — Client-side templating is not SSTI

**Type:** NEGATIVE  
**Domain:** injection  
**Status:** CURATED

## Claim rejected
“Handlebars in the browser evaluated my string ⇒ server-side template injection.”

## Why
SSTI requires **server** evaluation. Client XSS/template sinks are different classes.
