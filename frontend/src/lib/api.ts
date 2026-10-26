import { User, AuthTokens, Portfolio, Holding } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private getAccessToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("foliopulse_access_token");
  }

  private setTokens(tokens: { access_token: string; refresh_token?: string }) {
    if (typeof window === "undefined") return;
    localStorage.setItem("foliopulse_access_token", tokens.access_token);
    if (tokens.refresh_token) {
      localStorage.setItem("foliopulse_refresh_token", tokens.refresh_token);
    }
  }

  public clearTokens() {
    if (typeof window === "undefined") return;
    localStorage.removeItem("foliopulse_access_token");
    localStorage.removeItem("foliopulse_refresh_token");
    localStorage.removeItem("foliopulse_user");
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    const token = this.getAccessToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 204) {
      return {} as T;
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data?.detail || `API request failed with status ${response.status}`;
      throw new Error(errorMsg);
    }

    return data as T;
  }

  // --- Auth Endpoints ---
  async register(payload: { email: string; full_name: string; password: string }): Promise<AuthTokens> {
    const data = await this.request<AuthTokens>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    this.setTokens(data);
    return data;
  }

  async login(payload: { email: string; password: string }): Promise<AuthTokens> {
    const data = await this.request<AuthTokens>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    this.setTokens(data);
    return data;
  }

  async logout(): Promise<void> {
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("foliopulse_refresh_token") : null;
    if (refreshToken) {
      try {
        await this.request<void>("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // Ignore logout errors
      }
    }
    this.clearTokens();
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me");
  }

  // --- Portfolios Endpoints ---
  async listPortfolios(): Promise<Portfolio[]> {
    return this.request<Portfolio[]>("/portfolios");
  }

  async createPortfolio(payload: { name: string; description?: string; currency?: string }): Promise<Portfolio> {
    return this.request<Portfolio>("/portfolios", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getPortfolio(id: string): Promise<Portfolio> {
    return this.request<Portfolio>(`/portfolios/${id}`);
  }

  async deletePortfolio(id: string): Promise<void> {
    return this.request<void>(`/portfolios/${id}`, {
      method: "DELETE",
    });
  }

  // --- Holdings Endpoints ---
  async listHoldings(portfolioId: string): Promise<Holding[]> {
    return this.request<Holding[]>(`/portfolios/${portfolioId}/holdings`);
  }

  async addHolding(
    portfolioId: string,
    payload: {
      ticker: string;
      name?: string;
      quantity: number;
      average_cost: number;
      asset_class?: string;
      sector?: string;
    }
  ): Promise<Holding> {
    return this.request<Holding>(`/portfolios/${portfolioId}/holdings`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async deleteHolding(portfolioId: string, holdingId: string): Promise<void> {
    return this.request<void>(`/portfolios/${portfolioId}/holdings/${holdingId}`, {
      method: "DELETE",
    });
  }
}

export const api = new ApiClient();
