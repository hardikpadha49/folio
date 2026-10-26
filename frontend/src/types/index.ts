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

export interface ApiError {
  detail: string;
  type?: string;
}
