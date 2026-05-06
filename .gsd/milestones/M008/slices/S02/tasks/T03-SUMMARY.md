# T03 Summary: Define Response Metadata Contract

Status: ready for verification

## Contract

- D004 remains the compatibility envelope: `source`, `data_status`, `mock`, `message`, `updated_at`.
- PRD fields are additive aliases/metadata: `data_source`, `data_mode`, `as_of`, `fallback_reason`.
- `data_status` remains the authoritative top-level status until all clients migrate.
- Mixed AI responses must expose per-input `evidence` metadata so a generated answer does not hide sample or fallback sources.

## Artifact

- Updated `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md` with field mapping, scenario mapping, and combined AI response rules.
