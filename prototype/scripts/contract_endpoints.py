"""S02 数据契约端点 SSOT —— `CONTRACT_ENDPOINTS` + `EXEMPT_ENDPOINTS`

参见：
- `.gsd/DECISIONS.md::D004` —— 数据契约 6 值 enum (`real | mock | fallback | unavailable | empty | error`)
- `.gsd/DECISIONS.md::D005` —— 显式白名单豁免（不静默漏扫）

本模块是 `check_api_contract.py` / `smoke_test.py` 共享端点列表的单一来源（SSOT），
消除多地 drift。T06 已把 `CONTRACT_ENDPOINTS` 扩到全 ~30+ 条数据路由（覆盖 T01-T04
迁移成果），并把 `check_api_contract.py` 升级为强制三字段（source/data_status/mock）
+ 6 值 enum 校验 + mock⟺status=mock 一致性 + EXEMPT 显式 SKIP。

豁免策略（D005）：
控制接口 / 写操作 / 协议异类（如 WebSocket）不返回 `{data, source, data_status, mock}` 四元组。
显式白名单 `EXEMPT_ENDPOINTS` 让 "这条端点为什么没契约" 永远有书面答案。
"""

from __future__ import annotations


# 必须满足 D004 契约的数据路由（path, expected_source 命名空间）
# expected_source 用 prefix 匹配（actual == expected 或 actual.startswith(f"{expected}_")）
# 当 source 在 CI 运行时不确定（如 tushare token 缺失会切换到 sample_*），用空字符串
# 让 check_api_contract.py 跳过具体值校验（仍要求非空）。
#
# 命名空间清单：kpl / kpl_longhu_bang / kpl_sentiment / kpl_recommend /
# eastmoney_news / static_chain_registry / sample_chain / static_recommend_templates /
# llm_recommend / mysql_lab / tushare / sample_financials / static_industry_prosperity /
# static_macro_sample / sample_portfolio / static_meso_indicators / static_rotation_rules /
# transmission_rule_matrix / sample_research_announcements / sample_research_alt_data /
# sample_historical_prosperity / sample_engine
CONTRACT_ENDPOINTS: list[tuple[str, str]] = [
    # ── /api/market/* （短线主源 KPL：intraday + replay + sentiment）
    ("/api/market/limit-up", "kpl"),
    ("/api/market/broken", "kpl"),
    ("/api/market/hot-stocks", "kpl"),
    ("/api/market/anomaly", "kpl"),
    ("/api/market/summary", "kpl"),
    ("/api/market/ladder", "kpl"),
    ("/api/market/ladder-relay", "kpl"),
    ("/api/market/sectors", "kpl"),
    ("/api/market/limit-performance", "kpl"),
    ("/api/market/capital-flow", "kpl"),
    ("/api/market/rotation", "kpl"),
    ("/api/market/archive", "kpl"),
    ("/api/market/next-day-strategy", "kpl"),
    ("/api/market/sentiment-history", "kpl_sentiment"),
    ("/api/market/sentiment-phase", "kpl_sentiment"),
    ("/api/market/similar-days", "kpl_sentiment"),
    # ── /api/theme/*
    ("/api/theme/list", "kpl"),
    ("/api/theme/sectors", "kpl"),
    ("/api/theme/cycle-batch", "kpl"),
    # ── /api/longhu/*
    ("/api/longhu/seats", "kpl_longhu_bang"),
    ("/api/longhu/rank", "kpl_longhu_bang"),
    # ── /api/chain/*
    ("/api/chain/list", "static_chain_registry"),
    # ── /api/news/*
    ("/api/news/flash", "eastmoney_news"),
    ("/api/news/timeline", "eastmoney_news"),
    # ── /api/recommend/*
    ("/api/recommend/templates", "static_recommend_templates"),
    ("/api/recommend/strategies", "kpl_recommend"),
    # ── /api/analysis/*
    ("/api/analysis/broken-cases", "kpl"),
    ("/api/analysis/strategy-recommend", "kpl"),
    # ── /api/research/*
    ("/api/research/announcements", "sample_research_announcements"),
    ("/api/research/alt-data", "sample_research_alt_data"),
    ("/api/research/prosperity-cycle", "sample_historical_prosperity"),
    # ── /api/rotation/*
    ("/api/rotation/known-themes", "transmission_rule_matrix"),
    ("/api/rotation/novelty", "kpl"),
    ("/api/rotation/theme-history/{theme}", "kpl"),
    # ── /api/growth/* （景气度 / 价值持仓）
    ("/api/growth/macro", ""),  # tushare 或 static_macro_sample（按 token 切换）
    ("/api/growth/prosperity", "static_industry_prosperity"),
    ("/api/growth/portfolio", "sample_portfolio"),
    ("/api/growth/meso", "static_meso_indicators"),
    ("/api/growth/rotation", "static_rotation_rules"),
    # ── /api/value/*
    ("/api/value/screen", "sample_financials"),
    # diffusion / turning-points / weekly-report 的 source 形如
    # "static_industry_prosperity+diffusion_rule"——base 数据 + 规则/llm 派生层。
    # 用空串 sentinel 仅校验 source 非空，不绑定具体派生后缀。
    ("/api/value/diffusion", ""),
    ("/api/value/turning-points", ""),
    ("/api/value/weekly-report", ""),
    # ── /api/strategy/*
    ("/api/strategy/templates", ""),  # tushare 或 sample（CI 无 token 时切样例）
    # ── /api/ai/*
    # AI 端点 source 形如 "kpl+llm" (real path) 或 "kpl" (fallback)；用空串 sentinel
    # 仅校验非空，不绑定具体 LLM 拼接形式。
    ("/api/ai/headline", ""),
    ("/api/ai/replay-report", ""),
    # ── /api/etf/* （source 来自 data.data_source，CI 默认 sample_engine）
    ("/api/etf/rotation/dashboard", ""),
    # ── /api/lab/* （需 JWT；check_api_contract 会先 register 取 token）
    ("/api/lab/alert-rules", "mysql_lab"),
    ("/api/lab/style-combo", "mysql_lab"),
]


# 显式白名单豁免（D005）—— 控制接口 / 写操作 / 协议异类
# 每条带 1 行豁免理由注释（让审计可读）
EXEMPT_ENDPOINTS: list[tuple[str, str]] = [
    ("/api/auth/register", "控制/注册流"),
    ("/api/auth/login", "控制/登录"),
    ("/api/auth/me", "控制/JWT 验证"),
    ("/api/dashboards", "用户态 CRUD"),
    ("/api/dashboards/save", "用户态写入"),
    ("/api/events/track", "事件日志写入"),
    ("/api/payment/order", "商业化操作（占位 403）"),
    ("/api/payment/invite-codes", "邀请码 CRUD"),
    ("/api/style/onboarding", "问卷写入"),
    ("/api/watchlist", "自选股 CRUD"),
    ("/api/lab/alert-rules POST", "Lab 写入操作"),
    # ── /api/rotation/* POST 端点 —— 规则推演/预期差不走 KPL 数据源
    ("/api/rotation/simulate POST", "规则推演模拟（纯规则矩阵计算）"),
    ("/api/rotation/expectation-gap POST", "预期差评估（纯规则评分）"),
    ("/api/rotation/expectation-gap/batch POST", "批量预期差评估"),
    # ── M001/S03/T04 业主 admin 后台 —— Cookie 录入 / 健康面板 / 告警 ack
    ("/api/admin/kpl-cookie", "admin metadata-only 不返 data"),
    ("/api/admin/kpl-cookie POST", "admin Cookie 写入操作"),
    ("/api/admin/health/kpl", "admin 健康面板状态"),
    ("/api/admin/health/kpl/trigger POST", "admin 手动触发健康探测"),
    ("/api/admin/alerts", "admin 告警列表"),
    ("/api/admin/alerts/{id}/ack POST", "admin 告警 ack 写入操作"),
    ("/ws", "WebSocket 协议异类"),
]


# 需要 JWT 的契约端点（check_api_contract 会先 register 取 token 再带 Bearer 调用）
AUTH_REQUIRED_PATHS: set[str] = {
    "/api/lab/alert-rules",
    "/api/lab/style-combo",
    "/api/ai/replay-report",  # consume_quota('ai_report') 依赖 JWT
}


if __name__ == "__main__":
    print(
        f"contract_endpoints SSOT: CONTRACT={len(CONTRACT_ENDPOINTS)}, "
        f"EXEMPT={len(EXEMPT_ENDPOINTS)}, AUTH_REQUIRED={len(AUTH_REQUIRED_PATHS)}"
    )
    print("\nCONTRACT_ENDPOINTS:")
    for path, src in CONTRACT_ENDPOINTS:
        src_repr = src if src else "(any)"
        print(f"  {path:50s} → {src_repr}")
    print("\nEXEMPT_ENDPOINTS (D005 显式白名单):")
    for path, reason in EXEMPT_ENDPOINTS:
        print(f"  {path:30s} — {reason}")
