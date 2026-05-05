from __future__ import annotations

import logging
from typing import Optional

from packages.features.chain.data import INDUSTRY_CHAINS

logger = logging.getLogger(__name__)


def _match_chain(keyword: str) -> Optional[str]:
    for chain_name in INDUSTRY_CHAINS:
        if keyword in chain_name or chain_name in keyword:
            return chain_name
    return None


def _fetch_kpl_data() -> list[dict]:
    try:
        from packages.connectors.registry import get_kpl_realtime
        client = get_kpl_realtime()
        resp = client.get_concept_selected()
        if isinstance(resp, dict) and resp.get("_error"):
            logger.warning("KPL sentinel returned: %s", resp.get("_error"))
            return []
        if isinstance(resp, list):
            return resp
        items = resp.get("Data", resp.get("data", []))
        return items if isinstance(items, list) else []
    except Exception:
        logger.warning("KPL concept fetch failed", exc_info=True)
        return []


def analyze_event_chain(keyword: str) -> Optional[dict]:
    chain_name = _match_chain(keyword)
    if chain_name is None:
        logger.info("No chain match for keyword=%s", keyword)
        return None

    chain = INDUSTRY_CHAINS[chain_name]
    matched_chain = {
        "upstream": chain.get("upstream", []),
        "midstream": chain.get("midstream", []),
        "downstream": chain.get("downstream", []),
    }
    transmission_logic = chain.get("传导逻辑", "")
    transmission_lag = chain.get("传导时滞", "")

    result: dict = {
        "keyword": keyword,
        "chain_name": chain_name,
        "matched_chain": matched_chain,
        "transmission_logic": transmission_logic,
        "transmission_lag": transmission_lag,
        "kpl_enrichment": [],
        "llm_analysis": "",
    }

    kpl_data = _fetch_kpl_data()
    result["kpl_enrichment"] = kpl_data

    chain_data = {
        "chain_name": chain_name,
        "matched_chain": matched_chain,
        "transmission_logic": transmission_logic,
        "transmission_lag": transmission_lag,
    }

    try:
        from apps.ai.agents.agents import EventChainAgent
        agent = EventChainAgent()
        result["llm_analysis"] = agent.analyze_chain(keyword, chain_data, kpl_data)
    except Exception:
        logger.warning("LLM analysis failed for keyword=%s", keyword, exc_info=True)

    return result
