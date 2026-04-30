from __future__ import annotations

INDUSTRY_CHAINS: dict[str, dict] = {
    "芯片半导体": {
        "upstream": [
            {"name": "EDA/IP", "stocks": ["华大九天", "芯原股份", "概伦电子"]},
            {"name": "半导体材料", "stocks": ["沪硅产业", "安集科技", "南大光电"]},
            {"name": "半导体设备", "stocks": ["北方华创", "中微公司", "盛美上海"]},
        ],
        "midstream": [
            {"name": "芯片设计", "stocks": ["韦尔股份", "兆易创新", "卓胜微"]},
            {"name": "晶圆制造", "stocks": ["中芯国际", "华虹公司"]},
        ],
        "downstream": [
            {"name": "封装测试", "stocks": ["长电科技", "通富微电", "华天科技"]},
            {"name": "终端应用", "stocks": ["闻泰科技", "立讯精密"]},
        ],
        "传导逻辑": "政策/需求驱动 → 设备/材料先行 → 设计跟进 → 制造扩产 → 封测受益",
        "传导时滞": "1-5个交易日",
    },
    "新能源汽车": {
        "upstream": [
            {"name": "锂矿/碳酸锂", "stocks": ["天齐锂业", "赣锋锂业", "融捷股份"]},
            {"name": "正极材料", "stocks": ["容百科技", "当升科技", "德方纳米"]},
            {"name": "负极材料", "stocks": ["璞泰来", "杉杉股份", "贝特瑞"]},
            {"name": "电解液", "stocks": ["天赐材料", "新宙邦", "多氟多"]},
            {"name": "隔膜", "stocks": ["恩捷股份", "星源材质"]},
        ],
        "midstream": [
            {"name": "动力电池", "stocks": ["宁德时代", "比亚迪", "亿纬锂能", "国轩高科"]},
            {"name": "电池系统", "stocks": ["欣旺达", "鹏辉能源"]},
        ],
        "downstream": [
            {"name": "整车制造", "stocks": ["比亚迪", "长城汽车", "理想汽车"]},
            {"name": "充电桩", "stocks": ["特锐德", "盛弘股份", "通合科技"]},
        ],
        "传导逻辑": "锂价变动 → 材料成本传导 → 电池企业利润 → 整车定价 → 销量反馈",
        "传导时滞": "2-10个交易日",
    },
    "AI人工智能": {
        "upstream": [
            {"name": "AI芯片", "stocks": ["寒武纪", "海光信息", "景嘉微"]},
            {"name": "算力基础", "stocks": ["中科曙光", "浪潮信息", "紫光股份"]},
            {"name": "光模块", "stocks": ["中际旭创", "新易盛", "天孚通信"]},
        ],
        "midstream": [
            {"name": "大模型", "stocks": ["科大讯飞", "百度", "商汤"]},
            {"name": "AI框架/工具", "stocks": ["金山办公", "致远互联"]},
        ],
        "downstream": [
            {"name": "AI应用-教育", "stocks": ["网易有道", "鸿合科技"]},
            {"name": "AI应用-医疗", "stocks": ["卫宁健康", "创业慧康"]},
            {"name": "AI应用-金融", "stocks": ["同花顺", "恒生电子", "东方财富"]},
            {"name": "AI应用-自动驾驶", "stocks": ["德赛西威", "中科创达", "经纬恒润"]},
        ],
        "传导逻辑": "算力需求 → 芯片/光模块 → 大模型训练 → 应用落地 → 商业化",
        "传导时滞": "1-3个交易日(短期催化), 1-3个月(基本面)",
    },
    "医药生物": {
        "upstream": [
            {"name": "CXO", "stocks": ["药明康德", "康龙化成", "泰格医药"]},
            {"name": "原料药", "stocks": ["司太立", "普洛药业", "天宇股份"]},
        ],
        "midstream": [
            {"name": "创新药", "stocks": ["恒瑞医药", "百济神州", "信达生物"]},
            {"name": "仿制药", "stocks": ["华海药业", "科伦药业"]},
            {"name": "医疗器械", "stocks": ["迈瑞医疗", "联影医疗", "微创医疗"]},
        ],
        "downstream": [
            {"name": "医药流通", "stocks": ["国药控股", "华润医药", "上海医药"]},
            {"name": "连锁药店", "stocks": ["益丰药房", "大参林", "老百姓"]},
            {"name": "医疗服务", "stocks": ["爱尔眼科", "通策医疗"]},
        ],
        "传导逻辑": "政策/集采 → CXO订单 → 创新药获批 → 流通放量 → 终端受益",
        "传导时滞": "3-10个交易日",
    },
}


def get_chain(chain_name: str) -> dict | None:
    return INDUSTRY_CHAINS.get(chain_name)


def get_all_chain_names() -> list[str]:
    return list(INDUSTRY_CHAINS.keys())


def build_echarts_graph(chain_name: str) -> dict:
    chain = INDUSTRY_CHAINS.get(chain_name)
    if not chain:
        return {"nodes": [], "links": []}

    nodes = []
    links = []
    node_id = 0

    center_node = {"id": str(node_id), "name": chain_name, "category": "center", "symbolSize": 60}
    nodes.append(center_node)
    center_id = str(node_id)
    node_id += 1

    categories = [
        {"name": "center"},
        {"name": "upstream"},
        {"name": "midstream"},
        {"name": "downstream"},
        {"name": "stock"},
    ]

    for stream, stream_label in [("upstream", "上游"), ("midstream", "中游"), ("downstream", "下游")]:
        stream_node = {"id": str(node_id), "name": stream_label, "category": stream, "symbolSize": 40}
        nodes.append(stream_node)
        links.append({"source": center_id, "target": str(node_id)})
        stream_id = str(node_id)
        node_id += 1

        for segment in chain.get(stream, []):
            seg_node = {"id": str(node_id), "name": segment["name"], "category": stream, "symbolSize": 30}
            nodes.append(seg_node)
            links.append({"source": stream_id, "target": str(node_id)})
            seg_id = str(node_id)
            node_id += 1

            for stock_name in segment.get("stocks", [])[:3]:
                stock_node = {"id": str(node_id), "name": stock_name, "category": "stock", "symbolSize": 18}
                nodes.append(stock_node)
                links.append({"source": seg_id, "target": str(node_id)})
                node_id += 1

    return {"nodes": nodes, "links": links, "categories": categories}
