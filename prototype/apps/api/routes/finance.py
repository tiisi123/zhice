"""
财务/财报路由（PRD M4D-01~07）
基于东财（dfcf）数据源：
  GET  /finance/quote/{code}              快照行情
  GET  /finance/summary/{code}             财务摘要 N 期
  GET  /finance/profile/{code}             公司简介
  GET  /finance/announcements/{code}       公告列表（财报/业绩/合同）
  GET  /finance/research-reports/{code}    券商研报
  POST /finance/compare                    多公司财务对比（最多 5 只）
  POST /finance/explain-report             AI 财报解读（粘贴文本即可）
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

from packages.connectors.registry import get_dfcf

logger = logging.getLogger(__name__)
router = APIRouter()
_dfcf = get_dfcf()


def _meta(source: str, data_status: str, sample_mode: bool = False, message: str = "") -> dict:
    return {
        "source": source,
        "data_status": data_status,
        "mock": sample_mode,
        "message": message,
    }


@router.get("/quote/{code}")
def quote(code: str):
    data = _dfcf.get_quote(code)
    status = "unavailable" if data.get("error") else ("empty" if not data else "ok")
    return {**data, **_meta("dfcf", status, message=data.get("error", ""))}


@router.get("/summary/{code}")
def summary(code: str, n: int = Query(8, ge=1, le=24)):
    """近 n 期财务摘要（年/季报混合按报告期倒序）。"""
    data = _dfcf.get_financial_summary(code, n_periods=n)
    if data.get("error"):
        try:
            from packages.connectors.registry import get_tushare

            ts_data = get_tushare().get_financial_summary(code, n_periods=n)
            if ts_data.get("periods"):
                return {
                    **ts_data,
                    **_meta("tushare", "ok", message="东方财富异常，已使用 TuShare 财务摘要补充"),
                }
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"上游异常: {data['error']}")
    if not data.get("periods"):
        try:
            from packages.connectors.registry import get_tushare

            ts_data = get_tushare().get_financial_summary(code, n_periods=n)
            if ts_data.get("periods"):
                return {
                    **ts_data,
                    **_meta("tushare", "ok", message="东方财富无摘要数据，已使用 TuShare 财务摘要补充"),
                }
        except Exception:
            pass
    return {
        **data,
        **_meta("dfcf", "ok" if data.get("periods") else "empty"),
    }


@router.get("/profile/{code}")
def profile(code: str):
    try:
        data = _dfcf.get_company_profile(code) or {}
    except Exception as e:
        logger.warning("company profile fetch failed for %s: %s", code, e)
        data = {"error": str(e)}
    if data.get("error"):
        quote_data = {}
        try:
            quote_data = _dfcf.get_quote(code) or {}
        except Exception:
            quote_data = {}
        return {
            "code": code,
            "name": quote_data.get("name") or code,
            "industry": quote_data.get("industry") or "—",
            "summary": "",
            "data_source": "fallback",
            "warning": f"公司简介暂不可用：{data['error']}",
            **_meta("dfcf_profile_fallback", "partial", message=f"公司简介暂不可用：{data['error']}"),
        }
    return {**data, **_meta("dfcf", "ok" if data else "empty")}


@router.get("/announcements/{code}")
def announcements(
    code: str,
    days: int = Query(180, ge=7, le=730),
    kind: Optional[str] = Query(None, description="report/earnings/contract/shareholder/all"),
):
    items = _dfcf.get_announcements(code, days=days, kind=kind)
    return {"code": code, "items": items, "count": len(items), **_meta("dfcf", "ok" if items else "empty")}


@router.get("/research-reports/{code}")
def research_reports(code: str, n: int = Query(20, ge=1, le=50)):
    items = _dfcf.get_research_reports(code, n=n)
    return {"code": code, "items": items, "count": len(items), **_meta("dfcf", "ok" if items else "empty")}


# ============== 多公司对比（PRD：M4D-04 / M4D-06 复合能力） ==============
class CompareIn(BaseModel):
    codes: list[str] = Field(..., min_length=2, max_length=5)


@router.post("/compare")
def compare(inp: CompareIn):
    """多公司横向对比：取每只最新一期 + 估值快照，组装成可直接渲染的表格 + 雷达图数据。"""
    rows = []
    for code in inp.codes:
        q = _dfcf.get_quote(code) or {}
        s = _dfcf.get_financial_summary(code, n_periods=4) or {}
        latest_idx = 0 if s.get("periods") else -1
        row = {
            "code": code,
            "name": q.get("name") or code,
            "industry": q.get("industry"),
            "price": q.get("price"),
            "change_rate": q.get("change_rate"),
            "pe_ttm": q.get("pe_ttm"),
            "pb": q.get("pb"),
            "market_cap": q.get("market_cap"),         # 元
            "circ_cap": q.get("circ_cap"),
            # 最新一期财务
            "latest_period": s.get("periods", [None])[latest_idx] if latest_idx >= 0 else None,
            "revenue": (s.get("revenue") or [0])[latest_idx] if latest_idx >= 0 else 0,
            "net_profit": (s.get("net_profit") or [0])[latest_idx] if latest_idx >= 0 else 0,
            "roe": (s.get("roe") or [0])[latest_idx] if latest_idx >= 0 else 0,
            "eps": (s.get("eps") or [0])[latest_idx] if latest_idx >= 0 else 0,
            "gross_margin": (s.get("gross_margin") or [0])[latest_idx] if latest_idx >= 0 else 0,
            "yoy_revenue": (s.get("yoy_revenue") or [0])[latest_idx] if latest_idx >= 0 else 0,
            "yoy_profit": (s.get("yoy_profit") or [0])[latest_idx] if latest_idx >= 0 else 0,
            # 趋势
            "trend_revenue": s.get("revenue") or [],
            "trend_net_profit": s.get("net_profit") or [],
            "trend_roe": s.get("roe") or [],
            "trend_periods": s.get("periods") or [],
        }
        rows.append(row)

    # 排名（数值越大越好的指标）
    rank_keys = ["roe", "yoy_revenue", "yoy_profit", "gross_margin"]
    rankings: dict[str, list[str]] = {}
    for k in rank_keys:
        ranked = sorted(rows, key=lambda r: r.get(k) or 0, reverse=True)
        rankings[k] = [r["code"] for r in ranked]

    # PE 越小越好（剔除负值/0）
    valid_pe = [r for r in rows if (r.get("pe_ttm") or 0) > 0]
    rankings["pe_ttm_low"] = [r["code"] for r in sorted(valid_pe, key=lambda r: r["pe_ttm"])]

    return {
        "rows": rows,
        "rankings": rankings,
        "metric_labels": {
            "roe": "净资产收益率(%)",
            "yoy_revenue": "营收同比(%)",
            "yoy_profit": "净利润同比(%)",
            "gross_margin": "销售毛利率(%)",
            "pe_ttm_low": "PE-TTM（越低越好）",
        },
        **_meta("dfcf+compare_rule", "ok" if rows else "empty", message="多公司对比为东方财富数据汇总和规则排名"),
    }


# ============== AI 财报解读（PRD M4D-02 / M4D-05 雏形） ==============
class ExplainIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    period: Optional[str] = None
    text: str = Field(..., min_length=20, description="财报正文片段或业绩预告文本")


@router.post("/explain-report")
def explain_report(inp: ExplainIn):
    """
    AI 解读财报/业绩文本。
    输入：原文片段（用户可粘贴 PDF 解析后文本，或直接业绩预告全文）。
    输出：核心变化 / 关键科目异常 / 风险提示 / 一句话结论。
    """
    from apps.ai.agents.llm_client import llm

    head = f"【{inp.name or inp.code or '某公司'}】"
    if inp.period:
        head += f" 报告期：{inp.period}"

    prompt = f"""你是一位资深 A 股财报分析师，请对下面的财报/业绩公告进行结构化解读。

{head}

【正文】
{inp.text[:6000]}

请按以下 5 个部分输出 Markdown，每部分 2-4 行：

## 1. 核心变化
（营收/净利/毛利率等关键指标同比环比变化，给出具体百分比）

## 2. 业务亮点
（业务结构调整、产品突破、订单增长、新业务等）

## 3. 关键科目异常
（应收/存货/商誉/经营现金流等是否健康，重点关注异常波动）

## 4. 风险提示
（盈利可持续性、现金流、负债、行业景气度等）

## 5. 一句话结论
（用一句话总结业绩成色：超预期/符合预期/低于预期，并给出操作倾向）

注意：客观分析、引用正文数据；如正文信息不足请明确指出。
"""
    try:
        text = llm.chat(prompt)
        return {
            "code": inp.code,
            "name": inp.name,
            "period": inp.period,
            "analysis": text,
            "disclaimer": "AI 生成内容仅供参考，基于公开文本推演，不构成投资建议。",
            **_meta("user_text+llm", "ok", message="AI 解读基于用户输入文本"),
        }
    except Exception as e:
        logger.exception("explain_report failed")
        raise HTTPException(status_code=500, detail=f"AI 解读失败: {e}")


# ============== PDF 解析 + 一键解读（M4D-02 闭环） ==============
_MAX_PDF_SIZE = 30 * 1024 * 1024  # 30 MB
_MAX_TEXT_CHARS = 50_000


def _extract_pdf_text(content: bytes) -> str:
    """用 pypdf 抽 PDF 全文。抽取失败/扫描件返回空字符串。"""
    from io import BytesIO
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"未安装 pypdf：{e}")
    try:
        reader = PdfReader(BytesIO(content))
        chunks: list[str] = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(chunks).strip()
    except Exception as e:
        logger.warning("pdf extract failed: %s", e)
        return ""


@router.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    """
    上传财报 PDF，返回抽取的文本（前端可二次粘贴/编辑后再调 explain-report）。
    限制：≤30MB；返回前 50k 字符；扫描件无文本层会返回空。
    """
    content = await file.read()
    if len(content) > _MAX_PDF_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大，>{_MAX_PDF_SIZE // 1024 // 1024}MB")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    text = _extract_pdf_text(content)
    truncated = False
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS]
        truncated = True
    return {
        "filename": file.filename,
        "size": len(content),
        "char_count": len(text),
        "truncated": truncated,
        "text": text,
        "warning": "未识别到文本（可能是扫描件 PDF）" if not text else None,
        **_meta("uploaded_pdf+pypdf", "ok" if text else "empty", message="PDF 文本抽取结果"),
    }


@router.post("/explain-pdf")
async def explain_pdf(
    file: UploadFile = File(...),
    code: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    period: Optional[str] = Form(None),
):
    """
    一键流程：上传 PDF → 抽文本 → AI 结构化解读。
    返回同 /explain-report 的结构外，附带 extracted_text（截断版）以便前端展示。
    """
    content = await file.read()
    if len(content) > _MAX_PDF_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大，>{_MAX_PDF_SIZE // 1024 // 1024}MB")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    text = _extract_pdf_text(content)
    if not text:
        raise HTTPException(status_code=422, detail="PDF 无可提取文本（疑似扫描件，请改用粘贴文本）")

    # 截断喂给 LLM（保留前 6000 字，符合 prompt 约束）
    sample = text[:_MAX_TEXT_CHARS]
    inp = ExplainIn(code=code, name=name, period=period, text=sample)
    result = explain_report(inp)
    result["extracted_text_preview"] = sample[:2000]
    result["full_char_count"] = len(text)
    result.update(_meta("uploaded_pdf+pypdf+llm", "ok", message="AI 解读基于上传 PDF 抽取文本"))
    return result
