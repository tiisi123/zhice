# M009 Roadmap

## Vision
题材工坊成为 KPL 题材库、板块强度、涨停池和个股实时行情的统一入口，所有数据来源和缺口对用户可见。

## Success Criteria
- 用户可以打开“题材库”页签并看到真实或明确 fallback 的数据状态。
- 题材详情不再因 KPL 空 body 被误判为无题材。
- 后续 AI 分析可以拿到题材库证据包和匹配后的行情证据。

## Slices
- [x] **S01: 题材库最小纵切** `risk:high` `depends:[]`
  > After this: KPL 题材库连接器、API 和页面 Tab 可展示列表/详情/fallback 状态。
- [x] **S02: 题材成员行情匹配** `risk:medium` `depends:[S01]`
  > After this: 题材库成员按股票代码匹配 KPL 5000+ ranking，展示涨幅、价格、成交额、热度和缺失原因。
- [x] **S03: 题材库与板块强度匹配** `risk:medium` `depends:[S01]`
  > After this: 题材库条目可以匹配到板块强度/涨停池，显示匹配来源、置信度和冲突提示。
- [x] **S04: AI 题材证据包改造** `risk:medium` `depends:[S02,S03]`
  > After this: AI 分析题材时按用户问题动态选择日期和证据，不再固定套当前页空数据模板。
- [x] **S05: 端到端数据 QA 收口** `risk:low` `depends:[S04]`
  > After this: 输出题材工坊数据矩阵，列出无数据接口、fallback 原因和已知上游限制。

## Key Risks
- KPL 题材库老接口可能依赖 Cookie/旧 DB。
- 题材名与板块名匹配不可靠，需要置信度而非硬合并。
- 直接渲染 KPL HTML 有安全风险。

## Proof Strategy
先用单元测试锁定 KPL 参数和 normalization，再用 API contract 测试锁定 fallback，最后用前端构建/页面 smoke 验证展示。

## Verification Classes
- Connector unit
- API contract
- Frontend type/build
- Live endpoint smoke

## Definition of Done
对应 slice 的代码、测试和文档都落地；验证命令在最后一次代码修改后运行；未通过或不可验证的部分必须明确说明。

## Requirement Coverage
- M008 无 mock 数据契约：S01-S05
- KPL 优先实时/短线源：S01-S03
- AI 问题理解与动态证据：S04
- QA 数据矩阵：S05

## Boundary Map
S01 produces `/theme/library*` and normalized theme detail → S02 consumes theme member stock codes.
S02 produces enriched member quotes → S03 consumes quote and sector signals for matching display.
S03 produces matched theme-sector evidence → S04 consumes evidence for AI context builder.
S04 produces AI evidence routing → S05 verifies UI/API/AI consistency.
