# S04 Plan: Macro Industry Real Data

## Objective

Replace macro and industry static/sample data paths with real TuShare/DFCF adapters where available, while making unavoidable static fields explicit.

## Tasks

- [x] **T01: Locate macro and industry routes** `est:30m`
  - Files: `prototype/apps/api`, `prototype/packages/features`
  - Do: identify endpoints, adapters, sample arrays, and current frontend consumers.
  - Verify: add route map to inventory.

- [x] **T02: Implement real-source adapter for one macro indicator family** `est:90m`
  - Files: selected macro data module.
  - Do: fetch or cache PMI/CPI/PPI style data with `data_source`, `data_mode`, `as_of`.
  - Verify: tests mock provider response and fallback response.

- [x] **T03: Implement industry real-data adapter path** `est:90m`
  - Files: selected industry data module.
  - Do: use available TuShare/DFCF route for industry classification or daily industry data.
  - Verify: contract test asserts metadata and no silent sample output.

- [x] **T04: Add frontend stale/fallback display check** `est:45m`
  - Files: impacted web page/component.
  - Do: surface source/freshness or explicit unavailable state without cluttering main workflow.
  - Verify: focused frontend test or screenshot check.
