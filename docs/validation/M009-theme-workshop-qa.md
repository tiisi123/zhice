# M009 题材工坊 QA 矩阵

## 检查目标
- 题材库列表是否有真实或缓存采集数据。
- 题材详情是否能返回成员、简介、层级和正文。
- 题材成员是否匹配 KPL 5000+ 实时行情。
- 题材库名称是否匹配板块强度/涨停池。
- 所有无数据场景是否明确 `data_status/message`。

## 执行命令

先用 `theme_list.xlsx` 冷启动题材库缓存：

```powershell
cd prototype
python scripts/collect_kpl_theme_library.py --input-xlsx ..\docs\gsd-input\theme_list.xlsx --sheet hotplate_hotstock --limit 500
```

再跑 QA：

```powershell
cd prototype
python scripts/qa_theme_workshop_matrix.py
```

可指定交易日：

```powershell
$env:QA_TRADE_DATE='2026-05-07'
python scripts/qa_theme_workshop_matrix.py
```

## 判定
- `bugs=[]`：M009 数据链路通过当前环境 QA。
- `题材库列表没有可展示数据`：需要先运行 `scripts/collect_kpl_theme_library.py` 刷新本地缓存，或配置生产 KPL 题材库来源。
- `题材详情不可用`：KPL `InfoGet/Theme` 当前凭证/网关不可用；若 xlsx 缓存有成员，页面仍展示冷启动成员。
- `quote_match_status=unavailable`：KPL `RealRankingInfo_W8/NewStockRanking` 当前没有返回 5000+ 行情，属于实时行情源缺口。
- `成员未匹配行情`：ranking 有返回但该成员代码未命中，需要检查代码格式或日期。
