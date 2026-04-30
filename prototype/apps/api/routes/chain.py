from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.utils.contract import wrap_contract
from packages.features.chain.data import get_chain, get_all_chain_names, build_echarts_graph

router = APIRouter()


@router.get("/list")
def chain_list():
    names = get_all_chain_names()
    return wrap_contract(
        names,
        source="static_chain_registry",
        status="real",
        chains=names,
        count=len(names),
    )


@router.get("/{chain_name}")
def chain_detail(chain_name: str):
    chain = get_chain(chain_name)
    if not chain:
        raise HTTPException(status_code=404, detail=f"产业链 '{chain_name}' 不存在，可选: {get_all_chain_names()}")
    return wrap_contract(
        chain,
        source="sample_chain",
        status="real",
        name=chain_name,
    )


@router.get("/{chain_name}/graph")
def chain_graph(chain_name: str):
    try:
        graph = build_echarts_graph(chain_name)
        if not graph or not graph.get("nodes"):
            raise HTTPException(status_code=404, detail=f"产业链 '{chain_name}' 不存在，可选: {get_all_chain_names()}")
        return wrap_contract(
            graph,
            source="sample_chain",
            status="real",
            name=chain_name,
            graph=graph,
        )
    except HTTPException:
        raise
    except Exception as e:
        return wrap_contract(
            {},
            source="sample_chain",
            status="unavailable",
            message=f"构建产业链图谱失败: {str(e)}",
            name=chain_name,
            graph={},
        )
