from __future__ import annotations

from packages.jobs.tushare_sync import build_plan, run_sync


def test_tushare_sync_dry_run_without_token(tmp_path):
    result = run_sync(table="fund_daily", days=7, output=tmp_path, dry_run=True)

    assert result["dry_run"] is True
    assert result["configured"] is False
    assert result["row_count"] == 0
    assert result["written_files"] == []
    assert result["symbols"]
    assert "dry-run" in result["message"]


def test_tushare_sync_plan_contains_date_range(tmp_path):
    plan = build_plan("fund_daily", 3, tmp_path)

    assert plan["table"] == "fund_daily"
    assert plan["days"] == 3
    assert len(plan["start_date"]) == 8
    assert len(plan["end_date"]) == 8
    assert plan["output"] == str(tmp_path)
