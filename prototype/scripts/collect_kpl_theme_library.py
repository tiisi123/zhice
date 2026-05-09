from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


THEME_COLUMNS = [
    "theme_id",
    "theme_name",
    "theme_createtime",
    "theme_hot_num",
    "theme_zt_num",
]


def _clean_value(value: Any) -> Any:
    try:
        import pandas as pd

        if pd.isna(value):
            return ""
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _code6(value: Any) -> str:
    text = str(_clean_value(value)).strip()
    if not text:
        return ""
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6)[-6:] if digits else text[:6]


def _to_number(value: Any) -> float:
    try:
        if value in (None, "", "--"):
            return 0.0
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _normalize_theme_rows(raw_rows: list[dict[str, Any]], *, source: str) -> list[dict[str, Any]]:
    by_theme: dict[str, dict[str, Any]] = {}
    for raw in raw_rows:
        row = {str(k): _clean_value(v) for k, v in raw.items()}
        theme_id = str(row.get("theme_id") or "").strip()
        theme_name = str(row.get("theme_name") or "").strip()
        if not theme_id or not theme_name:
            continue
        item = by_theme.setdefault(
            theme_id,
            {
                "theme_id": theme_id,
                "theme_name": theme_name,
                "theme_createtime": row.get("theme_createtime") or "",
                "theme_hot_num": row.get("theme_hot_num") or 0,
                "theme_zt_num": row.get("theme_zt_num") or 0,
                "data_desc": row.get("data_desc") or "",
                "create_time": row.get("create_time") or "",
                "source": source,
                "members": [],
            },
        )
        item["theme_hot_num"] = max(_to_number(item.get("theme_hot_num")), _to_number(row.get("theme_hot_num")))
        item["theme_zt_num"] = max(_to_number(item.get("theme_zt_num")), _to_number(row.get("theme_zt_num")))
        if str(row.get("create_time") or "") > str(item.get("create_time") or ""):
            item["create_time"] = row.get("create_time") or ""
        member = {
            "stock_code": _code6(row.get("stock_code")),
            "stock_name": row.get("stock_name") or "",
            "stock_hot_num": row.get("stock_hot_num") or 0,
            "stock_tag_id": row.get("stock_tag_id") or "",
            "stock_tag_name": row.get("stock_tag_name") or "",
            "stock_tag_reason": row.get("stock_tag_reason") or "",
        }
        if member["stock_code"] or member["stock_name"]:
            item["members"].append(member)
    rows = list(by_theme.values())
    rows.sort(key=lambda item: (_to_number(item.get("theme_hot_num")), _to_number(item.get("theme_zt_num"))), reverse=True)
    return rows


def collect_theme_rows_from_xlsx(path: Path, sheet_name: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pandas/openpyxl are required to collect theme library from xlsx") from exc
    df = pd.read_excel(path, sheet_name=sheet_name or 0)
    missing = [col for col in THEME_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"xlsx missing required columns: {missing}")
    return _normalize_theme_rows(df.to_dict(orient="records"), source=f"xlsx:{path.name}")[: int(limit)]


def _connect_from_env():
    try:
        import pymysql
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pymysql is required to collect external KPL theme library") from exc

    return pymysql.connect(
        host=os.environ["KPL_THEME_DB_HOST"],
        port=int(os.environ.get("KPL_THEME_DB_PORT", "3306")),
        user=os.environ["KPL_THEME_DB_USER"],
        password=os.environ["KPL_THEME_DB_PASSWORD"],
        database=os.environ.get("KPL_THEME_DB_NAME", "daban"),
        charset="utf8mb4",
        connect_timeout=10,
        read_timeout=30,
        cursorclass=pymysql.cursors.DictCursor,
    )


def collect_theme_rows(limit: int = 500) -> list[dict[str, Any]]:
    conn = _connect_from_env()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    theme_id,
                    theme_name,
                    theme_createtime,
                    theme_hot_num,
                    theme_zt_num,
                    data_desc,
                    create_time,
                    stock_code,
                    stock_name,
                    stock_hot_num,
                    stock_tag_id,
                    stock_tag_name,
                    stock_tag_reason
                FROM kpl_home_theme_mes
                ORDER BY CAST(theme_hot_num AS UNSIGNED) DESC, CAST(theme_zt_num AS UNSIGNED) DESC, CAST(theme_createtime AS UNSIGNED) DESC
                LIMIT %s
                """,
                (int(limit) * 100,),
            )
            return _normalize_theme_rows(list(cur.fetchall()), source="external_kpl_home_theme_mes")[: int(limit)]
    finally:
        conn.close()


def write_cache(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    source = rows[0].get("source") if rows else "unknown"
    payload = {
        "source": source or "external_kpl_home_theme_mes",
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(rows),
        "data": rows,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect KPL theme library list from old kpl_home_theme_mes table.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--input-xlsx", default="", help="Cold-start from exported kpl_home_theme_mes xlsx.")
    parser.add_argument("--sheet", default="", help="Optional xlsx sheet name.")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "data" / "cache" / "kpl_theme_library.json"),
    )
    args = parser.parse_args()
    if args.input_xlsx:
        rows = collect_theme_rows_from_xlsx(Path(args.input_xlsx), sheet_name=args.sheet or None, limit=args.limit)
    else:
        rows = collect_theme_rows(limit=args.limit)
    write_cache(rows, Path(args.output))
    print(json.dumps({"ok": True, "rows": len(rows), "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
