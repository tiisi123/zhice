from __future__ import annotations

from datetime import datetime


def build_market_context(
    summary: dict,
    limit_up: list[dict],
    broken: list[dict],
    sectors: list[dict],
) -> str:
    tiers: dict[int, list[str]] = {}
    for s in limit_up:
        bc = s.get("board_count", 1) or 1
        tiers.setdefault(bc, []).append(s.get("stock_name", ""))

    tier_text = ""
    for bc in sorted(tiers.keys(), reverse=True):
        names = "、".join(tiers[bc][:5])
        extra = f"等{len(tiers[bc])}只" if len(tiers[bc]) > 5 else ""
        tier_text += f"  {bc}板: {names}{extra}\n"

    broken_names = "、".join([s.get("stock_name", "") for s in broken[:5]])

    sector_text = ""
    for s in (sectors or [])[:10]:
        if isinstance(s, dict):
            name = s.get("PlateName", s.get("plate_name", s.get("name", str(s))))
            change = s.get("ChangePercent", s.get("change_percent", ""))
            sector_text += f"  - {name} ({change}%)\n" if change else f"  - {name}\n"
        elif isinstance(s, (list, tuple)) and len(s) > 1:
            sector_text += f"  - {s[1]}\n"
        else:
            sector_text += f"  - {s}\n"

    return f"""## 今日市场数据 ({summary.get('trade_date', datetime.now().strftime('%Y-%m-%d'))})

### 市场概况
- 涨停: {summary.get('limit_up_count', 0)}家
- 炸板: {summary.get('broken_count', 0)}家
- 炸板率: {summary.get('broken_rate', 0)}%
- 跌停: {summary.get('limit_down_count', 0)}家
- 上涨: {summary.get('up_count', 0)}家 / 下跌: {summary.get('down_count', 0)}家
- 最高连板: {summary.get('max_board', 0)}板
- 市场情绪: {summary.get('sentiment_level', '未知')}

### 连板天梯
{tier_text}
### 炸板股(前5)
{broken_names}

### 强势板块(前10)
{sector_text}"""


def build_stock_context(stock: dict, themes: list[str]) -> str:
    return f"""## 个股数据
- 代码: {stock.get('code', '')}
- 名称: {stock.get('name', '')}
- 涨跌幅: {stock.get('change_rate', 0)}%
- 连板: {stock.get('board_count', 0)}板
- 涨停原因: {stock.get('reason', '')}
- 所属题材: {'、'.join(themes)}
- 封单金额: {stock.get('seal_amount', 0)}
- 换手率: {stock.get('turnover_ratio', 0)}%"""


def build_event_chain_context(keyword: str, chain_data: dict, kpl_data: list[dict]) -> str:
    chain_name = chain_data.get("chain_name", keyword)
    matched = chain_data.get("matched_chain", {})

    sections = []
    for stream, label in [("upstream", "上游"), ("midstream", "中游"), ("downstream", "下游")]:
        segments = matched.get(stream, [])
        if not segments:
            continue
        lines = []
        for seg in segments:
            stocks_str = "、".join(seg.get("stocks", [])[:5])
            lines.append(f"  - {seg.get('name', '')}: {stocks_str}")
        sections.append(f"### {label}\n" + "\n".join(lines))

    chain_text = "\n\n".join(sections)

    transmission = chain_data.get("transmission_logic", "")
    lag = chain_data.get("transmission_lag", "")

    kpl_text = ""
    if kpl_data:
        kpl_lines = []
        for item in kpl_data[:15]:
            name = item.get("Name", item.get("name", ""))
            change = item.get("ChangePercent", item.get("change_percent", ""))
            intensity = item.get("Intensity", item.get("intensity", ""))
            kpl_lines.append(f"  - {name}: 涨跌{change}%, 强度{intensity}")
        kpl_text = "\n### KPL实时概念数据\n" + "\n".join(kpl_lines)

    return f"""## 产业链: {chain_name}

{chain_text}

### 传导逻辑
{transmission}

### 传导时滞
{lag}
{kpl_text}"""


def build_theme_context(theme_name: str, stocks: list[dict]) -> str:
    stock_lines = ""
    for s in stocks[:10]:
        stock_lines += f"  - {s.get('stock_name', '')}: {s.get('change_rate', 0)}% 连板{s.get('board_count', 0)}\n"
    return f"""## 题材数据: {theme_name}
- 题材内个股数: {len(stocks)}

### 成分股(前10)
{stock_lines}"""
