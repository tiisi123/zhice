from __future__ import annotations

from apps.ai.agents.llm_client import llm
from apps.ai.prompts.templates import (
    MARKET_REPLAY,
    STOCK_INSIGHT,
    THEME_ANALYSIS,
    STRATEGY_DSL,
    BACKTEST_ANALYSIS,
    EVENT_CHAIN_ANALYSIS,
    BOARD_TRADING_ADVICE,
    ETF_ROTATION_ADVICE,
)
from apps.ai.context_builders.market_context import (
    build_market_context,
    build_stock_context,
    build_theme_context,
    build_event_chain_context,
    build_board_trading_context,
    build_etf_rotation_context,
)


class MarketReplayAgent:
    def generate_report(
        self, summary: dict, limit_up: list[dict], broken: list[dict], sectors: list[dict]
    ) -> str:
        context = build_market_context(summary, limit_up, broken, sectors)
        prompt = MARKET_REPLAY.format(context=context)
        return llm.chat(prompt)


class StockInsightAgent:
    def generate_summary(self, stock: dict, themes: list[str]) -> str:
        context = build_stock_context(stock, themes)
        prompt = STOCK_INSIGHT.format(context=context)
        return llm.chat(prompt)


class HotThemeAgent:
    def analyze_theme(self, theme_name: str, stocks: list[dict]) -> str:
        context = build_theme_context(theme_name, stocks)
        prompt = THEME_ANALYSIS.format(context=context)
        return llm.chat(prompt)


class StrategyBuilderAgent:
    def natural_language_to_dsl(self, user_input: str) -> str:
        prompt = STRATEGY_DSL.format(user_input=user_input)
        return llm.chat(prompt)


class EventChainAgent:
    def analyze_chain(self, keyword: str, chain_data: dict, kpl_data: list[dict]) -> str:
        context = build_event_chain_context(keyword, chain_data, kpl_data)
        prompt = EVENT_CHAIN_ANALYSIS.format(keyword=keyword, context=context)
        return llm.chat(prompt)


class BoardTradingAgent:
    def generate_advice(
        self,
        user_style: str,
        board_replay: dict,
        ladder: dict,
        top_traders: list[dict],
        backtest: dict | None = None,
    ) -> str:
        context = build_board_trading_context(board_replay, ladder, top_traders, backtest)
        prompt = BOARD_TRADING_ADVICE.format(user_style=user_style, context=context)
        return llm.chat(prompt)


class EtfRotationAgent:
    def generate_advice(
        self,
        user_style: str,
        signals: list[dict],
        backtest: dict | None = None,
    ) -> str:
        context = build_etf_rotation_context(signals, backtest)
        prompt = ETF_ROTATION_ADVICE.format(user_style=user_style, context=context)
        return llm.chat(prompt)


class BacktestAnalystAgent:
    def analyze_result(self, backtest_result: dict) -> str:
        import json
        context = json.dumps(backtest_result, ensure_ascii=False, indent=2)
        prompt = BACKTEST_ANALYSIS.format(context=context)
        return llm.chat(prompt)
