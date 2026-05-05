import { type Page } from '@playwright/test'

function envelope<T>(data: T, source = 'e2e_mock') {
  return {
    data,
    data_status: 'mock',
    source,
    mock: true,
    message: '',
    updated_at: '2026-01-15T10:00:00',
  }
}

function listResp<T>(data: T[], source = 'e2e_mock') {
  return {
    data,
    data_status: 'mock',
    source,
    mock: true,
    message: '',
  }
}

function jsonRoute(page: Page, pattern: string, body: unknown) {
  return page.route(pattern, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    }),
  )
}

// ── Replay page ──

const MARKET_SUMMARY = {
  trade_date: '2026-01-15',
  limit_up_count: 58,
  broken_count: 12,
  broken_rate: 0.207,
  seal_success_rate: 0.793,
  max_board: 7,
  sentiment_level: '偏强',
  sentiment_score: 72,
  up_count: 3200,
  down_count: 1600,
  limit_down_count: 3,
  total_volume: 1.12e12,
  prev_date: '2026-01-14',
}

const LADDER_DATA = {
  tiers: {
    '7板': [
      {
        stock_code: '000001',
        stock_name: '测试龙头',
        change_rate: 10.0,
        turnover_ratio: 5.2,
        reason: '人工智能',
        combined_reason: '人工智能+算力',
        related_plates: ['人工智能', '算力'],
        first_plate_name: '人工智能',
        time: '09:30:05',
        board_count: 7,
        non_restricted_capital: 8e9,
        total_capital: 1.2e10,
      },
    ],
    '首板': [
      {
        stock_code: '600001',
        stock_name: '首板测试',
        change_rate: 9.98,
        turnover_ratio: 8.1,
        reason: '芯片',
        combined_reason: '芯片+半导体',
        related_plates: ['芯片'],
        first_plate_name: '芯片',
        time: '10:15:22',
        board_count: 1,
        non_restricted_capital: 3e9,
        total_capital: 5e9,
      },
    ],
  },
  total: 58,
}

const SECTORS_DATA = [
  { PlateName: '人工智能', Intensity: 95, ChangePercent: 3.2, PlateID: 'AI001' },
  { PlateName: '芯片半导体', Intensity: 88, ChangePercent: 2.1, PlateID: 'CHIP01' },
  { PlateName: '新能源车', Intensity: 72, ChangePercent: 1.5, PlateID: 'NEV01' },
]

const RELAY_DATA = {
  trade_date: '2026-01-15',
  prev_date: '2026-01-14',
  relay: [
    { from_tier: 1, from_count: 30, promoted: 8, promoted_codes: [], survived: 0, broken: 5, broken_codes: [], relay_rate: 0.27 },
    { from_tier: 2, from_count: 10, promoted: 4, promoted_codes: [], survived: 0, broken: 2, broken_codes: [], relay_rate: 0.4 },
  ],
}

const CAPITAL_FLOW = [
  { name: '主力净流入', value: 5.2e9 },
  { name: '散户净流入', value: -3.1e9 },
]

export async function mockReplayPage(page: Page) {
  await jsonRoute(page, '**/api/market/summary*', { ...MARKET_SUMMARY, data_status: 'mock', source: 'e2e_mock', mock: true })
  await page.route(/\/api\/market\/ladder\?/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...LADDER_DATA, data_status: 'mock', source: 'e2e_mock', mock: true }) }),
  )
  await jsonRoute(page, '**/api/market/ladder-relay*', { ...RELAY_DATA, data_status: 'mock', source: 'e2e_mock', mock: true })
  await jsonRoute(page, '**/api/market/sectors*', envelope(SECTORS_DATA))
  await jsonRoute(page, '**/api/market/capital-flow*', envelope(CAPITAL_FLOW))
  await jsonRoute(page, '**/api/market/sentiment-phase*', envelope({ phase: '上升期', score: 72 }))
  await jsonRoute(page, '**/api/market/sentiment-history*', envelope([]))
  await jsonRoute(page, '**/api/analysis/broken-cases*', envelope([]))
  await jsonRoute(page, '**/api/market/next-day-strategy*', envelope({ scenarios: [] }))
  await jsonRoute(page, '**/api/market/rotation*', envelope([]))
  await jsonRoute(page, '**/api/theme/cycle-batch*', envelope([]))
}

// ── Intraday page ──

const LIMIT_UP_LIST = [
  {
    stock_code: '000888',
    stock_name: '盘中涨停A',
    change_rate: 10.01,
    turnover_ratio: 6.5,
    reason: '机器人',
    combined_reason: '机器人+自动化',
    related_plates: ['机器人'],
    first_plate_name: '机器人',
    time: '09:31:00',
    board_count: 2,
    non_restricted_capital: 4e9,
    total_capital: 6e9,
  },
]

export async function mockIntradayPage(page: Page) {
  await jsonRoute(page, '**/api/market/limit-up*', listResp(LIMIT_UP_LIST))
  await jsonRoute(page, '**/api/market/broken*', listResp([]))
  await jsonRoute(page, '**/api/market/hot-stocks*', listResp([]))
  await jsonRoute(page, '**/api/market/anomaly*', listResp([]))
  await jsonRoute(page, '**/api/market/sectors*', listResp(SECTORS_DATA))
}

// ── Event Chain page ──

const EVENT_CHAIN = {
  keyword: '芯片',
  chain_name: '半导体产业链',
  matched_chain: {
    upstream: ['光刻胶', '硅片'],
    midstream: ['晶圆代工', '封测'],
    downstream: ['消费电子', '汽车电子'],
  },
  transmission_logic: '上游材料涨价传导至中游代工成本',
  transmission_lag: '1-2个季度',
  kpl_enrichment: [],
  llm_analysis: '当前芯片产业链处于景气上行周期，上游材料供给偏紧。',
}

export async function mockEventChainPage(page: Page) {
  await jsonRoute(page, '**/api/analysis/event-chain*', envelope(EVENT_CHAIN))
}

// ── AI Agent page ──

const BOARD_TRADING_ADVICE = {
  advice: '当前市场情绪偏强，连板高度7板，建议关注人工智能方向的2-3板接力机会。',
  style: 'short',
  risk_preference: 'moderate',
}

const ETF_ROTATION_ADVICE = {
  advice: '建议配置科技类ETF 40%、消费类ETF 30%、债券ETF 30%。',
  style: 'growth',
  investment_horizon: 'medium',
  risk_preference: 'moderate',
}

const BOARD_REPLAY_DATA = {
  first_board: [
    {
      stock_code: '300001',
      stock_name: '复盘首板A',
      price: 15.6,
      change_rate: 10.0,
      limit_time: '09:35:00',
      seal_amount: 2.5e8,
      board_count: 1,
      sectors: ['人工智能'],
    },
  ],
  consecutive: [],
  broken: [],
}

export async function mockAIAgentPage(page: Page) {
  await jsonRoute(page, '**/api/ai/agent/board-trading', envelope(BOARD_TRADING_ADVICE))
  await jsonRoute(page, '**/api/ai/agent/etf-rotation', envelope(ETF_ROTATION_ADVICE))
  await jsonRoute(page, '**/api/analysis/board-replay*', envelope(BOARD_REPLAY_DATA))
  await jsonRoute(page, '**/api/etf/rotation/dashboard*', envelope({ etfs: [], links: [], trajectory: [], heatmap: { dates: [], items: [] }, summary: '', evaluation: '' }))
}

// ── Growth Workshop page ──

export async function mockGrowthWorkshopPage(page: Page) {
  await jsonRoute(page, '**/api/growth/macro*', envelope({ indicators: [{ name: 'PMI', value: 51.2, trend: 'up' }] }))
  await jsonRoute(page, '**/api/growth/prosperity*', envelope({ industries: [{ name: '半导体', score: 85, trend: 'up' }] }))
  await jsonRoute(page, '**/api/growth/rotation*', envelope([]))
  await jsonRoute(page, '**/api/etf/rotation/dashboard*', envelope({ etfs: [], links: [], trajectory: [], heatmap: { dates: [], items: [] }, summary: '', evaluation: '' }))
}

// ── Strategy Workshop page ──

export async function mockStrategyWorkshopPage(page: Page) {
  await jsonRoute(page, '**/api/strategy/**', envelope(null))
  await jsonRoute(page, '**/api/advanced-strategy/**', envelope(null))
  await jsonRoute(page, '**/api/ai/strategy-dsl*', envelope({ dsl: '' }))
}
