from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from apps.api.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self._client = httpx.Client(timeout=60)

    def chat(self, prompt: str, model: str = "gpt-4o") -> str:
        configured_provider = False
        if settings.preferred_ai_api_key:
            configured_provider = True
            try:
                return self._call_openai_compatible(
                    prompt,
                    settings.preferred_ai_base_url,
                    settings.preferred_ai_api_key,
                    settings.preferred_ai_chat_model,
                )
            except Exception as e:
                logger.warning("Preferred AI call failed, falling back to DeepSeek: %s", e)
        if settings.deepseek_api_key:
            configured_provider = True
            try:
                return self._call_deepseek(prompt, settings.deepseek_chat_model)
            except Exception as e:
                logger.warning("DeepSeek call failed, falling back to next provider: %s", e)
        if settings.openai_api_key and settings.openai_api_key.startswith("sk-"):
            configured_provider = True
            try:
                return self._call_openai(prompt, model)
            except Exception as e:
                logger.warning("OpenAI call failed, falling back to mock: %s", e)
        if settings.anthropic_api_key and settings.anthropic_api_key.startswith("sk-"):
            configured_provider = True
            try:
                return self._call_anthropic(prompt)
            except Exception as e:
                logger.warning("Anthropic call failed, falling back to mock: %s", e)
        if configured_provider:
            return (
                "AI 模型暂时不可用，已停止返回演示模板。请稍后重试，"
                "或检查首选 API / DeepSeek 网关状态。以上分析仅供参考，不构成投资建议。"
            )
        return self._mock_response(prompt)

    def fast_chat(self, prompt: str) -> str:
        if settings.preferred_ai_api_key:
            try:
                return self._call_openai_compatible(
                    prompt,
                    settings.preferred_ai_base_url,
                    settings.preferred_ai_api_key,
                    settings.preferred_ai_fast_model,
                )
            except Exception as e:
                logger.warning("Preferred AI fast call failed, falling back to DeepSeek fast: %s", e)
        if settings.deepseek_api_key:
            try:
                return self._call_deepseek(prompt, settings.deepseek_fast_model)
            except Exception as e:
                logger.warning("DeepSeek fast call failed, falling back to chat: %s", e)
        return self.chat(prompt)

    def _call_openai_compatible(self, prompt: str, base_url: str, api_key: str, model: str) -> str:
        base = base_url.rstrip("/")
        with self._client.stream(
            "POST",
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
        ) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return self._read_sse_chat_completion(resp)
            payload = json.loads(resp.read().decode("utf-8"))
            return payload["choices"][0]["message"]["content"]

    def _read_sse_chat_completion(self, resp: httpx.Response) -> str:
        parts: list[str] = []
        try:
            for raw_line in resp.iter_lines():
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        parts.append(str(content))
        except httpx.HTTPError:
            if parts:
                return "".join(parts)
            raise
        if parts:
            return "".join(parts)
        raise ValueError("SSE chat completion contained no content")

    def _call_deepseek(self, prompt: str, model: str) -> str:
        return self._call_openai_compatible(prompt, settings.deepseek_base_url, settings.deepseek_api_key, model)

    def _call_openai(self, prompt: str, model: str) -> str:
        resp = self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_anthropic(self, prompt: str) -> str:
        base = settings.anthropic_base_url.rstrip("/")
        resp = self._client.post(
            f"{base}/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    def _mock_response(self, prompt: str) -> str:
        p = prompt.lower()
        if any(kw in prompt for kw in ("打板策略", "打板标的", "连板梯队", "游资席位", "打板操作")):
            return ("### 1. 市场环境判断\n当前市场连板梯队健康，最高板空间充足，"
                    "晋级率维持在合理区间，打板环境偏暖，适合中等仓位参与。\n\n"
                    "### 2. 策略建议\n根据您的交易风格：\n"
                    "1. 关注首板放量突破品种，选择板块内辨识度最高的标的\n"
                    "2. 二板确认后可适当加仓，优先选择有游资席位加持的品种\n"
                    "3. 控制单票仓位不超过总仓位的20%\n\n"
                    "### 3. 重点关注标的\n"
                    "结合今日涨停复盘和游资动向，以下标的值得跟踪观察：\n"
                    "- 板块龙头封板稳固，次日关注溢价\n"
                    "- 游资介入品种关注资金持续性\n"
                    "- 首板放量品种关注次日竞价强度\n\n"
                    "### 4. 风险提示\n"
                    "- 炸板率偏高时降低参与仓位\n"
                    "- 高位股面临分歧风险，追涨需谨慎\n"
                    "- 注意大盘系统性风险对个股的压制\n\n"
                    "以上分析仅供参考，不构成投资建议。")
        if any(kw in prompt for kw in ("ETF轮动", "ETF配置", "轮动信号", "加仓信号", "减仓信号")):
            return ("### 1. 宏观环境研判\n当前市场风格偏向成长，行业轮动加速，"
                    "宽基指数震荡为主，结构性机会活跃。建议均衡配置宽基+行业ETF。\n\n"
                    "### 2. 配置建议\n根据您的投资偏好：\n"
                    "- 加仓信号品种可逐步建仓，分批买入控制成本\n"
                    "- 持有信号品种维持现有仓位，观察趋势变化\n"
                    "- 减仓信号品种建议逐步降低仓位，锁定收益\n"
                    "- 宽基ETF建议配置50%，行业ETF配置30%，预留20%现金\n\n"
                    "### 3. 策略解释\n"
                    "轮动信号基于三因子模型：动量因子(40%)反映近期趋势强度，"
                    "趋势因子(35%)判断中期方向，波动率安全因子(25%)控制风险。"
                    "当综合评分超过阈值时触发加仓信号，低于阈值触发减仓。\n\n"
                    "### 4. 风险提示\n"
                    "- 市场风格切换可能导致信号短期失效\n"
                    "- 行业ETF流动性差异较大，大额调仓注意冲击成本\n"
                    "- 历史回测不代表未来表现，需持续跟踪信号变化\n\n"
                    "以上分析仅供参考，不构成投资建议。")
        if "回测" in prompt or "绩效" in prompt or "total_return" in p:
            return ("### 绩效评价\n该策略整体表现中等偏上，年化收益为正，最大回撤可控，"
                    "夏普比率接近1.0，说明风险调整后收益合理。\n\n"
                    "### 优势与劣势\n**优势：**\n- 盈亏比大于1.5，盈利交易平均收益高于亏损\n"
                    "- 持有天数短，资金周转效率高\n\n**劣势：**\n- 胜率偏低，连续亏损影响心态\n"
                    "- 依赖短期波动，震荡市信号少\n\n"
                    "### 改进建议\n1. 加入情绪过滤，冰点/低迷时降低仓位\n"
                    "2. 调整止盈区间，验证更宽止盈能否提升盈亏比\n\n"
                    "### 适用环境\n适合情绪回暖至高潮阶段。不适合缩量震荡、情绪冰点期。\n\n"
                    "以上分析仅供参考，不构成投资建议。")
        if any(kw in prompt for kw in ("复盘报告", "市场总览", "今日市场", "涨停家数")):
            return ("### 1. 市场总览\n今日市场情绪偏暖，涨停家数较昨日增加，炸板率维持合理区间。\n\n"
                    "### 2. 主线题材\n- AI硬件：涨停5家，算力需求持续扩张\n"
                    "- 商业航天：涨停3家，政策催化持续\n\n"
                    "### 3. 龙头梯队\n最高板5连板，龙头地位稳固，跟风梯队活跃度一般。\n\n"
                    "### 4. 资金与情绪\n主力净流入偏正面，情绪处于回暖阶段。\n\n"
                    "### 5. 风险提示\n- 高位股面临分歧风险\n- 部分题材炒作至高潮，警惕退潮\n\n"
                    "### 6. 次日计划\n关注主线低吸机会，高位股谨慎追涨。\n\n"
                    "以上分析仅供参考，不构成投资建议。")
        if any(kw in prompt for kw in ("题材阶段", "板块分析", "题材分析", "哪个题材")):
            return ("### 题材阶段\n当前处于**启动期**，涨停家数持续增加，板块内资金聚集效应明显。\n\n"
                    "### 核心个股\n- 龙头股封板稳固，换手充分，辨识度高\n"
                    "- 跟风梯队中有2-3只独立逻辑品种值得关注\n\n"
                    "### 演化预判\n未来1-3天大概率进入加速期，关注龙头能否打出更高空间板。\n\n"
                    "以上分析仅供参考，不构成投资建议。")
        if any(kw in prompt for kw in ("个股数据", "涨停原因", "stock_code")):
            return ("### 发生了什么\n该股今日涨停，所属板块整体走强，封单稳固。\n\n"
                    "### 为什么重要\n板块内涨停家数增加，题材处于启动阶段，市场关注度提升。\n\n"
                    "### 怎么看\n关注明日溢价率及板块持续性，留意大盘情绪变化对个股的影响。\n\n"
                    "以上分析仅供参考，不构成投资建议。")
        from datetime import datetime as _dt
        return (f"你好！我是智策AI助手。当前时间: {_dt.now().strftime('%Y年%m月%d日 %H:%M')}。\n\n"
                "我可以帮你做以下分析：\n"
                "- **市场复盘**：生成每日复盘报告\n"
                "- **题材分析**：判断题材阶段和核心个股\n"
                "- **个股洞察**：分析个股涨停原因和关联\n"
                "- **策略回测**：将自然语言策略转换为DSL并回测\n\n"
                "当前处于模拟回复模式。配置 AI API Key 后可启用真实分析。\n\n"
                "以上分析仅供参考，不构成投资建议。")

    def close(self):
        self._client.close()


llm = LLMClient()
