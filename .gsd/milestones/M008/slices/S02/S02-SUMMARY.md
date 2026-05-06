# S02 Summary: Source Inventory And No Silent Mock

Status: completed

## Delivered

- Classified the main backend data paths by source mode: live, cache, static, fallback, sample, and mock.
- Added frontend assumptions and UI source-status gaps to the inventory.
- Defined the compatibility metadata contract between current D004 fields and PRD target fields.
- Patched `POST /api/ai/agent/etf-rotation` so sample ETF evidence is no longer returned as `real`.
- Added a focused API regression test for the ETF Agent contract.

## Artifacts

- `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md`
- `prototype/apps/api/routes/ai.py`
- `prototype/tests/api/test_ai_etf_agent_contract.py`
- `prototype/scripts/contract_endpoints.py`
- `prototype/scripts/verify_m003_s06_ai_agents.py`

## Verification

- `python -m py_compile prototype\apps\api\routes\ai.py prototype\tests\api\test_ai_etf_agent_contract.py prototype\scripts\verify_m003_s06_ai_agents.py prototype\scripts\contract_endpoints.py`
- `cd prototype && python -m pytest tests/api/test_ai_etf_agent_contract.py -q`
- `gsd headless --timeout 60000 recover`
- `git diff --check`

Result: ETF Agent contract test passed with `2 passed`; GSD recover rebuilt `1M/5S/21T`.

## Residual Risk

- `python prototype/scripts/check_no_mock.py` still fails on pre-existing frontend e2e/unit fixtures containing explicit mock test data. The current backend change removed its new `apps/api/routes/ai.py` hit; cleaning fixture allowlists should be handled as a separate task.
- Other high-risk paths remain for later slices or follow-up tasks: `agent/board-trading`, `/api/chain/*`, fixed-rule value/growth routes, and backtest default sample mode.
