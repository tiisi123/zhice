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


def build_board_trading_context(
    board_replay: dict,
    ladder: dict,
    top_traders: list[dict],
    backtest: dict | None = None,
) -> str:
    first_board = board_replay.get("first_board", [])
    consecutive = board_replay.get("consecutive", [])
    broken = board_replay.get("broken", [])

    fb_lines = ""
    for s in first_board[:8]:
        fb_lines += f"  - {s.get('stock_name', '')}({s.get('stock_code', '')}) 封单{s.get('seal_amount', 0)} 板块:{','.join(s.get('sectors', [])[:3])}\n"

    cb_lines = ""
    for s in sorted(consecutive, key=lambda x: x.get("board_count", 0), reverse=True)[:8]:
        cb_lines += f"  - {s.get('stock_name', '')}({s.get('stock_code', '')}) {s.get('board_count', 0)}板 封单{s.get('seal_amount', 0)}\n"

    broken_lines = ""
    for s in broken[:5]:
        broken_lines += f"  - {s.get('stock_name', '')}({s.get('stock_code', '')})\n"

    tier_stats = ladder.get("tier_stats", {})
    tier_text = ""
    for tier_name, stats in sorted(tier_stats.items(), key=lambda x: x[0], reverse=True):
        pr = stats.get("promotion_rate")
        pr_str = f"晋级率{pr:.1f}%" if pr is not None else ""
        sectors = [s.get("name", "") for s in stats.get("top_sectors", [])[:3]]
        tier_text += f"  - {tier_name}: {pr_str} 聚集板块:{','.join(sectors)}\n"

    famous_lines = ""
    for stock in top_traders[:5]:
        name = stock.get("stock_name", "")
        buy_famous = [s.get("famous_alias", "") for s in stock.get("buy_seats", []) if s.get("famous_alias")]
        sell_famous = [s.get("famous_alias", "") for s in stock.get("sell_seats", []) if s.get("famous_alias")]
        if buy_famous or sell_famous:
            parts = []
            if buy_famous:
                parts.append(f"买入:{','.join(buy_famous[:3])}")
            if sell_famous:
                parts.append(f"卖出:{','.join(sell_famous[:3])}")
            famous_lines += f"  - {name}: {' '.join(parts)}\n"

    bt_text = ""
    if backtest:
        bt_text = f"""
### 策略回测参考
- 胜率: {backtest.get('win_rate', 0):.1f}%
- 盈亏比: {backtest.get('profit_loss_ratio', 0):.2f}
- 年化收益: {backtest.get('annualized_return', 0):.2f}%
- 最大回撤: {backtest.get('max_drawdown', 0):.2f}%
- 最大连亏: {backtest.get('max_consecutive_loss', 0)}次
- 夏普比率: {backtest.get('sharpe_ratio', 0):.2f}"""

    return f"""## 涨停复盘数据

### 首板({len(first_board)}只)
{fb_lines}
### 连板({len(consecutive)}只)
{cb_lines}
### 炸板({len(broken)}只)
{broken_lines}
### 连板梯队
{tier_text}
### 知名游资动向
{famous_lines if famous_lines else '  暂无知名游资上榜'}
{bt_text}"""


def build_etf_rotation_context(
    signals: list[dict],
    backtest: dict | None = None,
) -> str:
    buy_lines = ""
    hold_lines = ""
    sell_lines = ""
    for s in signals:
        name = s.get("etf_name", s.get("name", ""))
        code = s.get("etf_code", s.get("code", ""))
        signal = s.get("signal", "")
        conf = s.get("confidence", 0)
        factors = s.get("factors", {})
        mom = factors.get("momentum", 0)
        trend = factors.get("trend", 0)
        vol = factors.get("volatility_safety", 0)
        line = f"  - {name}({code}) 置信度{conf} 动量{mom:.0f}/趋势{trend:.0f}/安全{vol:.0f}\n"
        if signal == "加仓":
            buy_lines += line
        elif signal == "减仓":
            sell_lines += line
        else:
            hold_lines += line

    bt_text = ""
    if backtest:
        bt_text = f"""
### 轮动策略回测
- 年化收益: {backtest.get('annualized_return', 0):.2f}%
- 最大回撤: {backtest.get('max_drawdown', 0):.2f}%
- 夏普比率: {backtest.get('sharpe_ratio', 0):.2f}
- ETF数量: {backtest.get('etf_count', 0)}
- 调仓次数: {len(backtest.get('rebalance_log', []))}"""

    return f"""## ETF轮动信号

### 加仓信号
{buy_lines if buy_lines else '  无'}

### 持有信号
{hold_lines if hold_lines else '  无'}

### 减仓信号
{sell_lines if sell_lines else '  无'}
{bt_text}"""


def build_theme_context(theme_name: str, stocks: list[dict]) -> str:
    stock_lines = ""
    for s in stocks[:10]:
        stock_lines += f"  - {s.get('stock_name', '')}: {s.get('change_rate', 0)}% 连板{s.get('board_count', 0)}\n"
    return f"""## 题材数据: {theme_name}
- 题材内个股数: {len(stocks)}

### 成分股(前10)
{stock_lines}"""
