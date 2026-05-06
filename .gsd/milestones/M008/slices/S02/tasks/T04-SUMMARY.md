# T04 Summary: Patch One Highest-Risk Silent Mock Path

Status: verified

## Change

- Patched `POST /api/ai/agent/etf-rotation`.
- The route now asks ETF signals/backtest for `mode="auto"` instead of forcing `sample`.
- It aggregates the evidence `data_mode` values into the top-level D004 envelope.
- All-sample ETF evidence now returns `data_status="mock"` and `mock=true` instead of looking like `real`.
- Mixed evidence returns `fallback`, and each evidence input exposes source/mode/status details.

## Verification

- `python -m py_compile prototype\apps\api\routes\ai.py prototype\tests\api\test_ai_etf_agent_contract.py`
- `cd prototype && python -m pytest tests/api/test_ai_etf_agent_contract.py -q`

Result: `2 passed`.
