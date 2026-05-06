from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from packages.connectors.tushare import TushareClient
from packages.features.etf.rotation import ETF_SERIES, _to_ts_code

SUPPORTED_TABLES = {"fund_daily"}
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "cache" / "tushare_sync"


def _date_range(days: int) -> tuple[str, str]:
    end = datetime.now()
    start = end - timedelta(days=max(days, 1))
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def build_plan(table: str, days: int, output: Path) -> dict[str, Any]:
    start_date, end_date = _date_range(days)
    if table not in SUPPORTED_TABLES:
        raise ValueError(f"unsupported table {table!r}; supported={sorted(SUPPORTED_TABLES)}")
    return {
        "table": table,
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "output": str(output),
        "symbols": [_to_ts_code(item["code"]) for item in ETF_SERIES],
    }


def run_sync(*, table: str, days: int, output: Path, dry_run: bool = False) -> dict[str, Any]:
    plan = build_plan(table, days, output)
    result: dict[str, Any] = {
        **plan,
        "dry_run": dry_run,
        "configured": False,
        "written_files": [],
        "row_count": 0,
    }
    if dry_run:
        result["message"] = "dry-run only; no TuShare token required and no files written"
        return result

    client = TushareClient()
    result["configured"] = client.configured
    if not client.configured:
        result["message"] = "TUSHARE_TOKEN missing; run with --dry-run or configure token"
        return result

    output.mkdir(parents=True, exist_ok=True)
    try:
        for ts_code in plan["symbols"]:
            rows = client.get_fund_daily(ts_code=ts_code, limit=max(days, 1))
            result["row_count"] += len(rows)
            target = output / f"{table}_{ts_code.replace('.', '_')}.json"
            target.write_text(
                json.dumps(
                    {
                        "table": table,
                        "ts_code": ts_code,
                        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "rows": rows,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            result["written_files"].append(str(target))
    finally:
        client.close()
    result["message"] = f"synced {result['row_count']} rows"
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync selected TuShare tables into local cache files.")
    parser.add_argument("--table", default="fund_daily", choices=sorted(SUPPORTED_TABLES))
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_sync(table=args.table, days=args.days, output=args.output, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.dry_run or result.get("configured") else 2


if __name__ == "__main__":
    raise SystemExit(main())
