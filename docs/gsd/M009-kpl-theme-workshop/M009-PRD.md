# M009 KPL 题材工坊改造 PRD

本文件镜像 `.gsd/milestones/M009/M009-CONTEXT.md`，用于产品/研发查看。核心目标：把 KPL 题材库、题材列表、题材详情和个股行情匹配接入题材工坊，并保证无数据时明确说明来源与缺口。

## 数据源顺序
- 题材库列表：KPL `HomeThemeList / HisHomeDingPan`。
- 题材库列表采集缓存：优先使用导出的 `docs/gsd-input/theme_list.xlsx` 冷启动导入到本地 `data/cache/kpl_theme_library.json`，该 xlsx 来自旧服务 `kpl_home_theme_mes`。
- 题材库详情：KPL `InfoGet / Theme / ID=<theme_id>`。
- 板块强度：KPL `ConceptSelected`。
- 板块成员：KPL `ZhiShuStockList_W8`，为空时用涨停池按 related_plates 派生。
- 个股实时行情：KPL `RealRankingInfo_W8 / NewStockRanking` 5000+ ranking。

## 展示思路
- 新增“题材库”页签。
- 左侧展示主题名、热度、涨停数、生成时间、涨幅。
- 右侧展示题材简介、成员股票、细分标签、产业链层级、正文、匹配板块和成员实时行情。
- `Introduction` 第一版转纯文本展示，后续如需富文本再加 sanitizer。
- `data_status` 显示在列表与详情区域，用户能看到 real/fallback/unavailable。

## 匹配题材工坊
- 第一层：`theme_id` 精确匹配 KPL 详情。
- 第二层：`theme_name` 与板块名做标准化匹配，支持相等、包含、简称别名。
- 第三层：成员 `stock_code` 与 KPL ranking 按 6 位代码匹配行情。
- 第四层：涨停池 related_plates 补充板块成员与涨停数，但标记为 fallback。

## 采集方式
- 冷启动运行：`python scripts/collect_kpl_theme_library.py --input-xlsx ..\docs\gsd-input\theme_list.xlsx --sheet hotplate_hotstock --limit 500`。
- 后续有外部旧库连接时，也可运行 `prototype/scripts/collect_kpl_theme_library.py` 从旧表只读采集。
- 采集连接信息只从环境变量读取：`KPL_THEME_DB_HOST/PORT/USER/PASSWORD/NAME`。
- API 优先读取本地缓存；缓存不存在时再尝试 KPL 直连接口与派生 fallback。
- 详情 `InfoGet/Theme` 不可用时，使用 xlsx 缓存里的 `members` 作为真实冷启动成员，并继续尝试匹配 KPL 5000+ 行情。

## 不做的事
- 不用 mock 填充 KPL 空响应。
- 不把题材库混入板块强度口径。
- 不在前端暴露 KPL token/user/cookie。
