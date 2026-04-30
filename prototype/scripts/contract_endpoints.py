"""S02/T04 数据契约端点 SSOT —— `CONTRACT_ENDPOINTS` + `EXEMPT_ENDPOINTS`

参见：
- `.gsd/DECISIONS.md::D004` —— 数据契约 6 值 enum (`real | mock | fallback | unavailable | empty | error`)
- `.gsd/DECISIONS.md::D005` —— 显式白名单豁免（不静默漏扫）

本模块是 `check_api_contract.py` / `check_realtime_sources.py` / `smoke_test.py` 三脚本共享端点列表的
单一来源（SSOT），消除三地 drift。T07 会进一步：
- 把 `CONTRACT_ENDPOINTS` 扩到全 ~28 条数据路由
- 把 `check_api_contract.py` 升级为强制三字段（source/data_status/mock）+ 6 值 enum 校验
- 把 `EXEMPT_ENDPOINTS` 接入静态扫描器（让豁免成为可审计元数据）

豁免策略（D005）：
控制接口 / 写操作 / 协议异类（如 WebSocket）不返回 `{data, source, data_status, mock}` 四元组。
显式白名单 `EXEMPT_ENDPOINTS` 让 "这条端点为什么没契约" 永远有书面答案。
"""

from __future__ import annotations


# 必须满足 D004 契约的数据路由（path, expected_source 命名空间）
# 注意：本 task (T04) 仅落地 5 个新增路由的契约 + SSOT 骨架；T07 会扩到全集 ~28 条
CONTRACT_ENDPOINTS: list[tuple[str, str]] = [
    # T04 — 5 路由 group B（首次入契约）
    ("/api/chain/list", "static_chain_registry"),
    ("/api/chain/{chain_name}", "sample_chain"),
    ("/api/chain/{chain_name}/graph", "sample_chain"),
    ("/api/news/flash", "eastmoney_news"),
    ("/api/news/timeline", "eastmoney_news"),
    ("/api/recommend/templates", "static_recommend_templates"),
    ("/api/recommend/strategies", "kpl_recommend"),
    ("/api/recommend/explain/{template_id}", "llm_recommend"),
    ("/api/market/sentiment-history", "kpl_sentiment"),
    ("/api/market/sentiment-phase", "kpl_sentiment"),
    ("/api/market/similar-days", "kpl_sentiment"),
    ("/api/lab/alert-rules", "mysql_lab"),
    ("/api/lab/style-combo", "mysql_lab"),
    # 后续 T07 会从 T01-T03 已迁移的 15 路由拉清单合并到这里
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
    ("/ws", "WebSocket 协议异类"),
]


if __name__ == "__main__":
    print(
        f"contract_endpoints SSOT: CONTRACT={len(CONTRACT_ENDPOINTS)}, EXEMPT={len(EXEMPT_ENDPOINTS)}"
    )
    print("\nCONTRACT_ENDPOINTS:")
    for path, src in CONTRACT_ENDPOINTS:
        print(f"  {path:50s} → {src}")
    print("\nEXEMPT_ENDPOINTS (D005 显式白名单):")
    for path, reason in EXEMPT_ENDPOINTS:
        print(f"  {path:30s} — {reason}")
