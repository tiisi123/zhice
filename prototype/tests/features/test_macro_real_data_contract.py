from __future__ import annotations

from packages.features.macro import data as macro_data


class _FakeMacroTushare:
    configured = True

    def _post(self, api_name: str, params: dict, fields: str):
        del params, fields
        rows = {
            "cn_pmi": [
                {"MONTH": "202604", "PMI010000": 51.2},
                {"MONTH": "202603", "PMI010000": 50.5},
            ],
            "cn_cpi": [
                {"month": "202604", "nt_yoy": 0.4},
                {"month": "202603", "nt_yoy": 0.3},
            ],
            "cn_ppi": [
                {"month": "202604", "ppi_yoy": -2.2},
                {"month": "202603", "ppi_yoy": -2.7},
            ],
            "cn_m": [
                {"month": "202604", "m2_yoy": 7.1},
                {"month": "202603", "m2_yoy": 7.0},
            ],
            "sf_month": [
                {"month": "202604", "inc_month": 61200},
                {"month": "202603", "inc_month": 58900},
            ],
        }
        return rows.get(api_name, [])


class _FakeIndustryTushare:
    configured = True

    def _post(self, api_name: str, params: dict, fields: str):
        del fields
        if api_name == "index_classify":
            return [{"index_code": "801080.SI", "industry_name": "电子"}]
        if api_name == "sw_daily":
            assert params["ts_code"] == "801080.SI"
            return [
                {"trade_date": "20260506", "close": 120.0, "pe": 30.5, "pb": 3.2, "pct_change": 1.5},
                {"trade_date": "20260331", "close": 112.0, "pe": 29.5, "pb": 3.1, "pct_change": 0.5},
                {"trade_date": "20260102", "close": 100.0, "pe": 28.0, "pb": 3.0, "pct_change": 0.2},
                {"trade_date": "20250930", "close": 96.0, "pe": 26.0, "pb": 2.9, "pct_change": 0.3},
                {"trade_date": "20251008", "close": 92.0, "pe": 25.0, "pb": 2.8, "pct_change": -0.1},
                {"trade_date": "20250701", "close": 90.0, "pe": 24.0, "pb": 2.7, "pct_change": 0.1},
            ]
        return []


def test_macro_real_rows_carry_source_mode_and_static_references():
    rows = macro_data._fetch_real_macro(_FakeMacroTushare())

    pmi = next(row for row in rows if row["name"] == "PMI")
    lpr = next(row for row in rows if row["name"] == "LPR-1Y")

    assert pmi["data_source"] == "tushare_cn_pmi"
    assert pmi["data_mode"] == "live"
    assert pmi["as_of"] == "2026-04"
    assert lpr["data_source"] == "static_macro_reference"
    assert lpr["data_mode"] == "static"
    assert lpr["fallback_reason"] == "indicator_not_available_in_current_tushare_adapter"


def test_macro_fallback_rows_are_explicit_sample(monkeypatch):
    class _Unconfigured:
        configured = False

    monkeypatch.setattr("packages.connectors.registry.get_tushare", lambda: _Unconfigured())

    rows = macro_data.get_macro_indicators()

    assert rows
    assert {row["data_mode"] for row in rows} == {"sample"}
    assert {row["data_source"] for row in rows} == {"static_macro_sample"}
    assert all(row["fallback_reason"] == "tushare_unavailable_or_empty" for row in rows)


def test_industry_real_rows_carry_source_mode_and_as_of():
    rows = macro_data._fetch_real_prosperity(_FakeIndustryTushare())

    assert rows
    assert rows[0]["industry"] == "电子"
    assert rows[0]["data_source"] == "tushare_sw_daily"
    assert rows[0]["data_mode"] == "live"
    assert rows[0]["as_of"] == "2026-05-06"
