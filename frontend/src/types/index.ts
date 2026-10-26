export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Portfolio {
  id: string;
  name: string;
  description: string | null;
  currency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  holding_count: number;
}

export interface Holding {
  id: string;
  portfolio_id: string;
  ticker: string;
  name: string | null;
  quantity: number;
  average_cost: number;
  asset_class: string;
  sector: string | null;
  invested_value: number;
  created_at: string;
  updated_at: string;
}

export interface HoldingValuation {
  holding_id: string;
  ticker: string;
  name: string | null;
  asset_class: string;
  sector: string | null;
  quantity: number;
  average_cost: number;
  cost_basis: number;
  market_price: number | null;
  quote_currency: string | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_percent: number | null;
  allocation_percent: number | null;
  day_change: number | null;
  day_change_percent: number | null;
  price_timestamp: string | null;
  data_status: "VALID" | "STALE" | "UNPRICED" | "CONVERSION_FAILED" | "FALLBACK";
  status_note: string | null;
}

export interface PortfolioValuation {
  portfolio_id: string;
  portfolio_name: string;
  reporting_currency: string;
  total_cost_basis: number;
  total_market_value: number | null;
  total_unrealized_pnl: number | null;
  total_unrealized_pnl_percent: number | null;
  day_pnl: number | null;
  holdings_count: number;
  valued_holdings_count: number;
  valuation_complete: boolean;
  as_of: string;
  holdings: HoldingValuation[];
}

export interface CSVRowError {
  row: number;
  column: string;
  message: string;
  raw_value?: string;
}

export interface CSVHoldingRow {
  ticker: string;
  name: string | null;
  quantity: number;
  average_cost: number;
  asset_class: string;
  sector: string | null;
  invested_value: number;
}

export interface CSVPreviewResponse {
  total_rows: number;
  valid_rows_count: number;
  errors_count: number;
  valid_rows: CSVHoldingRow[];
  errors: CSVRowError[];
  can_commit: boolean;
}

export interface CSVCommitResponse {
  portfolio_id: string;
  imported_count: number;
  message: string;
}

export interface ApiError {
  detail: string;
  type?: string;
}
