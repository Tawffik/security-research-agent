# CASE-0039 — Second-order injection (store now, execute later)

**Type:** CASE  
**Status:** CURATED (Tier B)  
**Domain:** injection  
**Generalizable:** true

## Security property
data stored from user input must remain parameterized at every later sink

## Observation pattern (when vulnerable)
Benign-looking store; later admin/report/job path evaluates it as code/SQL/template

## Hypothesis
sink_trusts_stored_data_as_trusted

## Minimum experiment
1. Store unique marker via low-privilege path  
2. Trigger secondary processor (report, search, render)  
3. Observe evaluation differential

## Evidence required
Store + secondary path observations

## Disproof
Secondary path always parameterized/encoded

## Root cause
“Trusted because it came from DB” fallacy
