from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    _HAS_APSCHEDULER = True
except ImportError:
    _HAS_APSCHEDULER = False

from packages.connectors.kpl.client import KplClient
from packages.features.market import build_market_summary

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "cache"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def pull_market_snapshot():
    """收盘后拉取当日行情快照并缓存到本地 JSON 文件"""
    from apps.api.config import settings

    trade_date = datetime.now().strftime("%Y-%m-%d")
    logger.info("Scheduled: pulling market snapshot for %s", trade_date)

    try:
        kpl = KplClient(
            user_id=settings.kpl_user_id,
            token=settings.kpl_token,
            device_id=settings.kpl_device_id,
            version=settings.kpl_version,
        )
        kpl_stats = kpl.get_market_statistics(trade_date)
        limit_up = kpl.get_limit_up(trade_date)
        broken = kpl.get_broken(trade_date)
        sectors = kpl.get_concept_selected(trade_date)

        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = trade_date

        snapshot = {
            "trade_date": trade_date,
            "pulled_at": datetime.now().isoformat(),
            "summary": summary,
            "limit_up_count": len(limit_up),
            "broken_count": len(broken),
            "sector_count": len(sectors),
            "limit_up": limit_up[:50],
            "broken": broken[:30],
            "sectors": sectors[:30],
        }

        _ensure_dir()
        out_path = DATA_DIR / f"snapshot_{trade_date}.json"
        out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Scheduled: snapshot saved to %s", out_path)

        kpl.close()
    except Exception:
        logger.exception("Scheduled: failed to pull market snapshot")


def pull_sentiment_record():
    """收盘后记录当日情绪数据到累积文件，用于情绪周期图"""
    from apps.api.config import settings

    trade_date = datetime.now().strftime("%Y-%m-%d")
    logger.info("Scheduled: recording sentiment for %s", trade_date)

    try:
        kpl = KplClient(
            user_id=settings.kpl_user_id,
            token=settings.kpl_token,
            device_id=settings.kpl_device_id,
            version=settings.kpl_version,
        )
        kpl_stats = kpl.get_market_statistics(trade_date)
        limit_up = kpl.get_limit_up(trade_date)
        broken = kpl.get_broken(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)

        record = {
            "date": trade_date,
            "limit_up": summary["limit_up_count"],
            "broken": summary["broken_count"],
            "broken_rate": summary["broken_rate"],
            "max_board": summary["max_board"],
            "sentiment": summary["sentiment_level"],
            "score": summary["sentiment_score"],
            "up": summary["up_count"],
            "down": summary["down_count"],
        }

        _ensure_dir()
        history_path = DATA_DIR / "sentiment_history.json"
        history: list[dict] = []
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception:
                history = []

        existing_dates = {r["date"] for r in history}
        if trade_date not in existing_dates:
            history.append(record)
            history.sort(key=lambda x: x["date"])
            if len(history) > 365:
                history = history[-365:]
            history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Scheduled: sentiment record appended (%d total)", len(history))

        kpl.close()
    except Exception:
        logger.exception("Scheduled: failed to record sentiment")


def generate_daily_report():
    """收盘后自动生成 AI 复盘报告并归档"""
    trade_date = datetime.now().strftime("%Y-%m-%d")
    logger.info("Scheduled: generating daily report for %s", trade_date)

    try:
        snapshot_path = DATA_DIR / f"snapshot_{trade_date}.json"
        if not snapshot_path.exists():
            logger.warning("Scheduled: snapshot not found, skipping report generation")
            return

        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        summary = snapshot.get("summary", {})
        limit_up = snapshot.get("limit_up", [])
        broken = snapshot.get("broken", [])
        sectors = snapshot.get("sectors", [])

        from apps.ai.agents.agents import MarketReplayAgent
        agent = MarketReplayAgent()
        report = agent.generate_report(summary, limit_up, broken, sectors)

        from apps.api.db import execute
        execute(
            "INSERT INTO reports_archive(trade_date, kind, title, content, summary) VALUES (?,?,?,?,?)",
            (trade_date, "daily", f"{trade_date} AI复盘报告", report, report[:200]),
        )
        logger.info("Scheduled: daily report generated and archived for %s", trade_date)
    except Exception:
        logger.exception("Scheduled: failed to generate daily report")


# ============== PRD US-004：研究池价格异动 + 财报公告扫描 ==============
def _is_trading_hours() -> bool:
    """判定当前是否为 A 股交易时段（9:25-11:35 / 12:55-15:05），含集合竞价/盘后 5 分钟缓冲。"""
    now = datetime.now()
    if now.weekday() > 4:
        return False
    hm = now.hour * 60 + now.minute
    return (9 * 60 + 25 <= hm <= 11 * 60 + 35) or (12 * 60 + 55 <= hm <= 15 * 60 + 5)


def scan_watchlist_alerts():
    """
    每分钟（仅交易时段）扫描所有用户研究池，命中即写入 watch_alerts 表，
    去重键 (user_id, code, kind, trade_date)，前端 hook 会自动拉取展示。
    """
    if not _is_trading_hours():
        return
    try:
        from apps.api.db import query_all, execute
        from apps.api.routes.watchlist import compute_alerts_for_user

        users = query_all("SELECT DISTINCT user_id FROM watchlist LIMIT 200")
        if not users:
            return
        total = 0
        for u in users:
            uid = u["user_id"]
            try:
                hits = compute_alerts_for_user(uid)
            except Exception:
                logger.exception("compute_alerts_for_user(%s) failed", uid)
                continue
            for a in hits:
                try:
                    execute(
                        """INSERT OR IGNORE INTO watch_alerts
                           (user_id, code, name, kind, message, change_rate, trade_date)
                           VALUES (?,?,?,?,?,?,?)""",
                        (uid, a["code"], a["name"], a["kind"], a["message"],
                         a.get("change_rate", 0), a["trade_date"]),
                    )
                    total += 1
                except Exception:
                    logger.exception("insert watch_alert failed: %s", a)
        if total:
            logger.info("scan_watchlist_alerts: persisted %d hits across %d users", total, len(users))
    except Exception:
        logger.exception("scan_watchlist_alerts failed")


def scan_announcements_for_watchlist():
    """
    每天早盘前 8:30 扫描所有用户研究池里股票当日新公告（业绩/年报/合同），
    命中即写入 watch_alerts，前端打开会看到。
    """
    try:
        from apps.api.db import query_all, execute
        from packages.connectors.registry import get_dfcf

        dfcf = get_dfcf()
        users = query_all(
            "SELECT DISTINCT user_id, code, name FROM watchlist"
        )
        if not users:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        total = 0
        # 按 code 聚合，避免对同一股票重复请求
        codes_seen: dict[str, list[dict]] = {}
        for u in users:
            codes_seen.setdefault(u["code"], []).append(u)
        for code, owners in codes_seen.items():
            try:
                anns = dfcf.get_announcements(code, days=2, kind="all", n=10)
            except Exception:
                continue
            today_anns = [a for a in anns if (a.get("notice_date") or "").startswith(today)]
            if not today_anns:
                continue
            for owner in owners:
                for a in today_anns[:3]:
                    title = a.get("title") or ""
                    # 关键字粗判异动类
                    kind = "report" if any(k in title for k in ("年度报告", "季度报告", "半年度报告")) else \
                        "earnings" if any(k in title for k in ("业绩预", "业绩快报")) else \
                        "contract" if "合同" in title or "中标" in title else \
                        "ann"
                    try:
                        execute(
                            """INSERT OR IGNORE INTO watch_alerts
                               (user_id, code, name, kind, message, change_rate, trade_date)
                               VALUES (?,?,?,?,?,?,?)""",
                            (owner["user_id"], code, owner["name"] or code, kind,
                             f"📢 {title}", 0, today),
                        )
                        total += 1
                    except Exception:
                        logger.exception("insert ann alert failed")
        logger.info("scan_announcements_for_watchlist: persisted %d announcement alerts", total)
    except Exception:
        logger.exception("scan_announcements_for_watchlist failed")


scheduler = None


def persist_daily_snapshots():
    """15:50 收盘后将当日短线核心数据落库，供历史查询和相似日分析。"""
    import json
    try:
        from apps.api.db import execute as db_exec
        from packages.connectors.registry import get_kpl
        from packages.features.market import build_market_summary

        trade_date = datetime.now().strftime("%Y-%m-%d")
        kpl = get_kpl()
        limit_up = kpl.get_limit_up(trade_date)
        broken = kpl.get_broken(trade_date)
        summary = build_market_summary(kpl.get_market_statistics(trade_date), limit_up, broken)

        db_exec(
            """INSERT OR REPLACE INTO daily_market_snapshot
               (trade_date, limit_up_count, broken_count, broken_rate, seal_success_rate,
                max_board, sentiment_level, sentiment_score, up_count, down_count,
                limit_down_count, total_volume)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (trade_date, summary.get("limit_up_count", 0), summary.get("broken_count", 0),
             summary.get("broken_rate", 0), summary.get("seal_success_rate", 0),
             summary.get("max_board", 0), summary.get("sentiment_level", ""),
             summary.get("sentiment_score", 0), summary.get("up_count", 0),
             summary.get("down_count", 0), summary.get("limit_down_count", 0),
             summary.get("total_volume", 0)),
        )

        for s in limit_up:
            db_exec(
                """INSERT OR REPLACE INTO limit_up_pool
                   (trade_date, stock_code, stock_name, board_count, limit_time, reason, first_plate, change_rate)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (trade_date, s.get("stock_code", ""), s.get("stock_name", ""),
                 s.get("board_count", 1), s.get("time", ""), s.get("reason", ""),
                 s.get("first_plate_name", ""), s.get("change_rate", 0)),
            )

        for s in broken:
            db_exec(
                """INSERT OR REPLACE INTO broken_pool
                   (trade_date, stock_code, stock_name, board_count, broken_time, reason_raw, change_rate)
                   VALUES (?,?,?,?,?,?,?)""",
                (trade_date, s.get("stock_code", ""), s.get("stock_name", ""),
                 s.get("board_count", 1), s.get("time", ""), s.get("reason", ""),
                 s.get("change_rate", 0)),
            )

        # 连板天梯
        tier_map: dict[int, list[str]] = {}
        for s in limit_up:
            bc = s.get("board_count", 1)
            if bc >= 2:
                tier_map.setdefault(bc, []).append(s.get("stock_code", ""))
        for tier, codes in tier_map.items():
            leader = next((s for s in limit_up if s.get("stock_code") == codes[0]), {})
            db_exec(
                """INSERT OR REPLACE INTO board_ladder_snapshot
                   (trade_date, tier, stock_codes, count, leader_code, leader_name)
                   VALUES (?,?,?,?,?,?)""",
                (trade_date, tier, json.dumps(codes), len(codes),
                 codes[0] if codes else "", leader.get("stock_name", "")),
            )

        # 题材快照
        try:
            sectors = kpl.get_concept_selected(trade_date) or []
            for i, sec in enumerate(sectors[:20]):
                name = sec.get("PlateName") or sec.get("concept_name") or ""
                if not name:
                    continue
                db_exec(
                    """INSERT OR REPLACE INTO theme_daily_snapshot
                       (trade_date, theme_name, limit_up_count, change_percent, intensity, rank_pos)
                       VALUES (?,?,?,?,?,?)""",
                    (trade_date, name, sec.get("LimitUpNum", 0),
                     sec.get("ChangePercent", 0), sec.get("Intensity", 0), i + 1),
                )
        except Exception:
            logger.debug("persist theme_daily_snapshot failed")

        logger.info("persist_daily_snapshots: saved %d limit_up, %d broken for %s",
                    len(limit_up), len(broken), trade_date)
    except Exception:
        logger.exception("persist_daily_snapshots failed")


if _HAS_APSCHEDULER:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    scheduler.add_job(
        pull_market_snapshot,
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="pull_market_snapshot",
        replace_existing=True,
    )

    scheduler.add_job(
        pull_sentiment_record,
        CronTrigger(hour=15, minute=35, day_of_week="mon-fri"),
        id="pull_sentiment_record",
        replace_existing=True,
    )

    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=15, minute=45, day_of_week="mon-fri"),
        id="generate_daily_report",
        replace_existing=True,
    )

    # PRD US-004：交易时段每 60s 扫研究池价格异动
    scheduler.add_job(
        scan_watchlist_alerts,
        IntervalTrigger(seconds=60),
        id="scan_watchlist_alerts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 15:50 每日短线核心数据沉淀
    scheduler.add_job(
        persist_daily_snapshots,
        CronTrigger(hour=15, minute=50, day_of_week="mon-fri"),
        id="persist_daily_snapshots",
        replace_existing=True,
    )

    # 每日 8:30 扫描研究池财报/公告
    scheduler.add_job(
        scan_announcements_for_watchlist,
        CronTrigger(hour=8, minute=30, day_of_week="mon-fri"),
        id="scan_announcements_for_watchlist",
        replace_existing=True,
    )

    # M001/S03/T05: KPL realtime/history 健康双探测，30 分钟一次。
    # max_instances=1 + coalesce=True：单 worker 跑长时不会堆叠多个实例，
    # APScheduler 漏触发后 catch-up 时也只跑 1 次（避免 Cookie 一短期失效就
    # 写一坨重复 system_alerts 行 / 一封邮件被发 N 次）。
    from apps.api.services.kpl_health import probe_history, probe_realtime

    scheduler.add_job(
        probe_realtime,
        IntervalTrigger(minutes=30),
        id="kpl_realtime_health",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        probe_history,
        IntervalTrigger(minutes=30),
        id="kpl_history_health",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def start_scheduler():
    if not _HAS_APSCHEDULER:
        logger.warning("APScheduler not installed, scheduled tasks disabled. Run: pip install apscheduler>=3.10")
        return
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info(
            "Scheduler started: pull_market_snapshot @15:30, pull_sentiment_record @15:35"
            " + kpl_realtime_health/kpl_history_health @30min"
        )


def stop_scheduler():
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
