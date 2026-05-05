// M001/S01 escape-hatch types for dynamic API responses & loose Antd row shapes.
// S02 (data contract slice) will narrow these per-route. Using `any` here is
// explicit and gated; future code should prefer concrete interfaces below.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyData = any
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyRecord = Record<string, any>

export interface HeadlineResp {
  trade_date: string
  headline: string
}

export interface MarketSummary {
  trade_date: string
  limit_up_count: number
  broken_count: number
  broken_rate: number
  seal_success_rate?: number
  max_board: number
  sentiment_level: string
  sentiment_score: number
  up_count: number
  down_count: number
  limit_down_count: number
  total_volume: number
  prev_date?: string
  prev?: {
    limit_up_count?: number
    broken_count?: number
    broken_rate?: number
    seal_success_rate?: number
    max_board?: number
    sentiment_level?: string
  }
}

export interface LimitUpStock {
  stock_code: string
  stock_name: string
  change_rate: number
  turnover_ratio: number
  reason: string
  combined_reason: string
  related_plates: string[]
  first_plate_name: string
  time: string | null
  board_count: number
  non_restricted_capital: number
  total_capital: number
  leader_rank?: number
  is_leader?: boolean
}

export interface BoardTier {
  [tierName: string]: LimitUpStock[]
}

export interface LadderData {
  tiers: BoardTier
  total: number
}

export interface Sector {
  PlateName?: string
  concept_name?: string
  Intensity?: number
  concept_intensity?: number
  ChangePercent?: number
  concept_increase?: number
  PlateID?: string
  [key: string]: unknown
}

export interface Theme {
  id: string
  name: string
  hot_num: number
  limit_up_count: number
  stage: string | null
}

export interface RelayItem {
  from_tier: number
  from_count: number
  promoted: number
  promoted_codes: string[]
  survived: number
  broken: number
  broken_codes: string[]
  relay_rate: number
}

export interface RelayData {
  trade_date: string
  prev_date: string | null
  relay: RelayItem[]
  note?: string
}

export interface StockDetail {
  found: boolean
  message?: string
  stock_code?: string
  stock_name?: string
  change_rate?: number
  board_count?: number
  kline_label?: string
  reason?: string
  themes?: {
    related_plates: string[]
    main_theme: string
    hot_score: number
  }
  capital_flow?: {
    turnover_ratio: number
    non_restricted_capital: number
    total_capital: number
    estimated_net_inflow: number
  }
  linked_stocks?: Array<{
    code: string
    name: string
    change_rate: number
    board_count: number
  }>
}

export interface BacktestResult {
  strategy_name: string
  total_return: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  calmar_ratio: number
  profit_loss_ratio: number
  total_trades: number
  avg_hold_days: number
}

export interface PortfolioStock {
  code: string
  name: string
  price: number
  cost: number
  pnl: number
  pnl_rate: number
  pe: number
  pe_percentile: number
  roe: number
  div_yield: number
  market_value: number
}

export interface PortfolioData {
  total_value: number
  total_pnl: number
  total_pnl_rate: number
  stocks: PortfolioStock[]
}

// M001/S02 D004 数据契约 SSOT —— 与后端 packages/shared/types.py::DataStatus / ApiMeta 一一对应
// 参见 .gsd/DECISIONS.md::D004。S02 起所有数据卡片的 meta 走这两个类型。
export type DataStatus = 'real' | 'mock' | 'fallback' | 'unavailable' | 'empty' | 'error'

export interface ApiMeta {
  data_status: DataStatus
  source: string
  mock: boolean
  message?: string
  name?: string
}

export interface BoardTradingInput {
  style?: string
  risk_preference?: string
  focus_sectors?: string[]
}

export interface BoardTradingAdvice {
  advice: string
  style: string
  risk_preference: string
}

export interface EtfRotationInput {
  style?: string
  investment_horizon?: string
  risk_preference?: string
}

export interface EtfRotationAdvice {
  advice: string
  style: string
  investment_horizon: string
  risk_preference: string
}

export interface ContractEnvelope<T> {
  data: T
  data_status: DataStatus
  source: string
  mock: boolean
  message: string
  updated_at: string
  trade_date?: string
}

// M004/S01 — board-replay structured response
export interface BoardReplayStock {
  stock_code: string
  stock_name: string
  price: number
  change_rate: number
  limit_time: string
  seal_amount: number
  board_count: number
  sectors: string[]
}

export interface BoardReplayData {
  first_board: BoardReplayStock[]
  consecutive: BoardReplayStock[]
  broken: BoardReplayStock[]
}

// M004/S01 — top-traders (famous seats)
export interface EnrichedSeat {
  name: string
  famous_alias: string | null
}

export interface TopTraderStock {
  stock_code: string
  stock_name: string
  change_rate: number
  net_amount: number
  amount: number
  float_mv: number
  turnover_ratio: number
  concepts: string[]
  buy_seats: EnrichedSeat[]
  sell_seats: EnrichedSeat[]
  t_seats: EnrichedSeat[]
}

// M004/S02 — event chain
export interface EventChainData {
  keyword: string
  chain_name: string
  matched_chain: {
    upstream: string[]
    midstream: string[]
    downstream: string[]
  }
  transmission_logic: string
  transmission_lag: string
  kpl_enrichment: AnyData[]
  llm_analysis: string
}

// M004/S03 — ETF rotation backtest
export interface EtfRebalanceAllocation {
  code: string
  name: string
  weight: number
}

export interface EtfBacktestResult {
  strategy_name: string
  data_mode: string
  data_source: string
  total_return: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  total_trades: number
  equity_curve: { day: number; value: number }[]
  rebalance_log: { day: number; allocations: EtfRebalanceAllocation[] }[]
  etf_count: number
}

// M004/S04 — board strategy backtest
export interface BoardBacktestTradeEntry {
  date: string
  exit_date: string
  stock: string
  code: string
  direction: string
  hold_days: number
  pnl: number
  result: string
}

export interface BoardBacktestResult {
  strategy_name: string
  data_mode: string
  data_source: string
  total_return: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  profit_loss_ratio: number
  max_consecutive_loss: number
  total_trades: number
  win_trades: number
  loss_trades: number
  avg_hold_days: number
  equity_curve: { date: string; value: number }[]
  trade_log: BoardBacktestTradeEntry[]
}

export interface RegisterPayload {
  phone: string
  password: string
  nickname?: string
  invite_code: string
}
