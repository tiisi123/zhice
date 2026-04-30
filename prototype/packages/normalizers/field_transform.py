from __future__ import annotations

from datetime import datetime


def transform_fields(
    data_list: list[list] | list[dict],
    col_names: list[str] | None = None,
    comment_map: dict[str, str] | None = None,
) -> list[dict]:
    if not data_list:
        return []

    first = data_list[0]

    if isinstance(first, list) and col_names:
        result = []
        for row in data_list:
            record = {}
            for i, val in enumerate(row):
                if i < len(col_names):
                    record[col_names[i]] = val
            result.append(record)
        return result

    if isinstance(first, dict) and comment_map:
        reverse = {v: k for k, v in comment_map.items()}
        result = []
        for row in data_list:
            record = {}
            for k, v in row.items():
                mapped = reverse.get(k, k)
                record[mapped] = v
            result.append(record)
        return result

    return [dict(enumerate(row)) if isinstance(row, list) else row for row in data_list]


def convert_time_fields(record: dict, fields: list[str]) -> dict:
    for f in fields:
        val = record.get(f)
        if isinstance(val, (int, float)) and val > 1_000_000_000:
            try:
                record[f] = datetime.fromtimestamp(val).strftime("%H:%M:%S")
            except (ValueError, OSError):
                pass
    return record
