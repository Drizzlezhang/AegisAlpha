// === Pipeline ===
export interface PipelineLatest {
  pipeline_id: string;
  mode: "full" | "lightweight" | "manual";
  tickers: string[];
  recommendations: Recommendation[];
  health_scores: Record<string, number>;
}

export interface PipelineEvent {
  type:
    | "agent_start"
    | "agent_complete"
    | "agent_failed"
    | "pipeline_complete"
    | "trigger_fired";
  pipeline_run_id: number;
  pipeline_mode: "full" | "lightweight";
  agent_name?: string;
  ticker?: string;
  timestamp: string;
  data?: unknown;
}

// === Portfolio ===
export interface PortfolioSnapshot {
  total_nav: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  delta_dollars: number;
  cash_ratio: number;
}

export interface Position {
  id: number;
  account: string;
  ticker: string;
  pos_type: "stock" | "call" | "put";
  quantity: number;
  avg_cost: number;
  current_price: number;
  strike?: number;
  expiry?: string;
  option_type?: "call" | "put";
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  iv: number;
  delta_dollars: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  entry_mode: "passive" | "active_left" | "active_right" | "cc" | "sell_put";
  grade: string;
  health_score: number;
  dte: number;
}

export interface GreeksSummary {
  total_delta: number;
  total_gamma: number;
  total_theta: number;
  total_vega: number;
  total_delta_dollars: number;
}

// === Recommendations ===
export interface Recommendation {
  id: number;
  ticker: string;
  action: "buy" | "sell" | "hold";
  direction: "bullish" | "bearish" | "neutral";
  strategy: string;
  entry_mode: "active_left" | "active_right" | "cc" | "sell_put";
  rationale: string;
  score: number;
  urgency: "high" | "medium" | "low";
  risk_gate_status: "passed" | "blocked";
  block_reason?: string;
  created_at: string;
}

export interface StrategyComparison {
  strategy_name: string;
  cost: number;
  max_profit: number;
  max_loss: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  scenario: string;
}

export interface ScenarioPnl {
  scenario: "target" | "sideways" | "stop_loss";
  days: number[];
  pnl_values: number[];
}

// === Triggers ===
export interface Trigger {
  id: number;
  ticker: string;
  type: string;
  params: Record<string, unknown>;
  suggested_action: string;
  valid_until: string;
  status: "pending" | "triggered" | "expired" | "cancelled";
}

// === Flows ===
export interface EtfFlow {
  ticker: string;
  name: string;
  flow_7d: number;
  flow_30d: number;
  flow_pct: number;
}

export interface SectorFlow {
  sector: string;
  flow_7d: number;
  intensity: number;
}

export interface SmartMoneyData {
  ticker: string;
  direction_bias: "bullish" | "bearish" | "neutral";
  smart_money_score: number;
  unusual_options: UnusualOption[];
  narrative: string;
}

export interface UnusualOption {
  strike: number;
  expiry: string;
  option_type: "call" | "put";
  premium: number;
  oi_change: number;
  volume: number;
}

// === Health ===
export interface HealthScore {
  ticker: string;
  score: number;
  alerts: string[];
}
