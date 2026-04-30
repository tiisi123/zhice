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
