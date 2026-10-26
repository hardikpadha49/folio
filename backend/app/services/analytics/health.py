"""
FolioPulse AI — Portfolio Health Score Engine

Calculates an institutional-grade 0–100 Portfolio Health Score based on 4 pillars:
1. Diversification Quality (30%)
2. Concentration Risk Guard (25%)
3. Downside Resilience & Drawdown Buffer (25%)
4. Risk-Adjusted Return Efficiency (20%)

Handles insufficient historical data explicitly without manufacturing confident scores.
Identifies concrete strengths and key vulnerability flags.
"""
import logging
from typing import Dict, List, Optional

from app.models.user import Portfolio, Holding
from app.schemas.analytics import (
    HealthScoreResponse,
    HealthScoreComponent,
)
from app.services.analytics.risk import RiskEngine, get_risk_engine
from app.services.analytics.diversification import DiversificationEngine, get_diversification_engine
from app.services.market_data.base import HistoricalData

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "The Portfolio Health Score is an internal analytical metric provided for informational and educational "
    "purposes only. It does not constitute financial advice, an investment guarantee, or a prediction of future performance."
)


class HealthScoreEngine:
    """Evaluates multi-factor portfolio health and robustness."""

    def __init__(
        self,
        risk_engine: Optional[RiskEngine] = None,
        diversification_engine: Optional[DiversificationEngine] = None,
    ):
        self.risk_engine = risk_engine or get_risk_engine()
        self.diversification_engine = diversification_engine or get_diversification_engine()

    async def calculate_health(
        self,
        portfolio: Portfolio,
        period: str = "1y",
        custom_history: Optional[Dict[str, HistoricalData]] = None,
    ) -> HealthScoreResponse:
        holdings: List[Holding] = portfolio.holdings or []

        if not holdings:
            return HealthScoreResponse(
                portfolio_id=portfolio.id,
                overall_score=0.0,
                rating="Critical",
                status="EMPTY",
                components=[],
                key_strengths=[],
                key_risks=["Portfolio has 0 holdings."],
                disclaimer=DISCLAIMER,
            )

        # 1. Evaluate Diversification
        div_res = await self.diversification_engine.calculate_diversification(
            portfolio, custom_history=custom_history
        )
        div_score = div_res.score

        # 2. Evaluate Concentration Guard
        cost_map = {h.ticker: h.quantity * h.average_cost for h in holdings}
        total_cost = sum(cost_map.values()) if cost_map else 1.0
        sorted_weights = sorted([c / total_cost for c in cost_map.values()], reverse=True)
        top_1 = sorted_weights[0] if sorted_weights else 0.0
        top_3 = sum(sorted_weights[:3]) if sorted_weights else 0.0

        # Concentration score:
        # Penalize if top 1 > 20% or top 3 > 50%
        conc_penalty = 0.0
        if top_1 > 0.20:
            conc_penalty += (top_1 - 0.20) * 150.0  # e.g. 40% top 1 -> 30 pt penalty
        if top_3 > 0.50:
            conc_penalty += (top_3 - 0.50) * 80.0
        conc_score = max(0.0, min(100.0, 100.0 - conc_penalty))

        # 3. Evaluate Risk & Downside
        risk_res = await self.risk_engine.calculate_risk(
            portfolio, period=period, custom_history=custom_history
        )

        has_sufficient_history = (risk_res.observation_count >= 15) and (risk_res.status == "VALID")

        if not has_sufficient_history:
            # Report insufficient data honestly rather than manufacturing synthetic health
            return HealthScoreResponse(
                portfolio_id=portfolio.id,
                overall_score=round(div_score * 0.5 + conc_score * 0.5, 1),
                rating="Moderate",
                status="INSUFFICIENT_DATA",
                components=[
                    HealthScoreComponent(
                        factor="Diversification Quality",
                        score=round(div_score, 1),
                        weight=0.5,
                        impact="Neutral",
                        detail=f"Structural diversification score: {div_score:.1f}/100.",
                    ),
                    HealthScoreComponent(
                        factor="Concentration Guard",
                        score=round(conc_score, 1),
                        weight=0.5,
                        impact="Neutral",
                        detail=f"Top holding represents {top_1*100:.1f}% of invested capital.",
                    ),
                ],
                key_strengths=["Basic structural holdings allocation mapped."],
                key_risks=[
                    "Insufficient historical market data (< 15 trading days) to calculate downside risk and Sharpe ratios reliably."
                ],
                disclaimer=DISCLAIMER,
            )

        # Downside resilience score (based on Max Drawdown and 95% CVaR)
        # Max Drawdown: 0-10% -> 100; 10-25% -> 80-60; 25-45% -> 60-20
        max_dd = risk_res.max_drawdown
        if max_dd <= 0.10:
            downside_score = 100.0 - (max_dd / 0.10) * 15.0
        elif max_dd <= 0.25:
            downside_score = 85.0 - ((max_dd - 0.10) / 0.15) * 25.0
        else:
            downside_score = max(10.0, 60.0 - ((max_dd - 0.25) / 0.25) * 50.0)

        # Sharpe ratio efficiency score
        sharpe = risk_res.sharpe_ratio or 0.0
        if sharpe >= 1.5:
            efficiency_score = 100.0
        elif sharpe >= 1.0:
            efficiency_score = 80.0 + ((sharpe - 1.0) / 0.5) * 20.0
        elif sharpe >= 0.5:
            efficiency_score = 60.0 + ((sharpe - 0.5) / 0.5) * 20.0
        elif sharpe >= 0.0:
            efficiency_score = 40.0 + (sharpe / 0.5) * 20.0
        else:
            efficiency_score = max(10.0, 40.0 + (sharpe * 20.0))

        # Weighted composite score
        weights = [0.30, 0.25, 0.25, 0.20]
        scores = [div_score, conc_score, downside_score, efficiency_score]
        overall = round(sum(w * s for w, s in zip(weights, scores)), 1)

        # Rating classification
        if overall >= 85:
            rating = "Excellent"
        elif overall >= 70:
            rating = "Strong"
        elif overall >= 55:
            rating = "Moderate"
        elif overall >= 40:
            rating = "Fragile"
        else:
            rating = "Critical"

        components = [
            HealthScoreComponent(
                factor="Diversification Quality",
                score=round(div_score, 1),
                weight=0.30,
                impact="Positive" if div_score >= 65 else "Caution",
                detail=f"Breadth across sectors and asset classes ({div_res.rating}).",
            ),
            HealthScoreComponent(
                factor="Concentration Guard",
                score=round(conc_score, 1),
                weight=0.25,
                impact="Positive" if conc_score >= 70 else "Negative",
                detail=f"Largest position {top_1*100:.1f}%; Top 3 hold {top_3*100:.1f}%.",
            ),
            HealthScoreComponent(
                factor="Downside Resilience",
                score=round(downside_score, 1),
                weight=0.25,
                impact="Positive" if downside_score >= 70 else "Caution",
                detail=f"Historical max drawdown is {max_dd*100:.1f}%.",
            ),
            HealthScoreComponent(
                factor="Risk-Adjusted Efficiency",
                score=round(efficiency_score, 1),
                weight=0.20,
                impact="Positive" if efficiency_score >= 60 else "Caution",
                detail=f"Sharpe Ratio: {sharpe:.2f} (Risk-Free: {risk_res.risk_free_rate*100:.1f}%).",
            ),
        ]

        # Key strengths & risks
        strengths = []
        risks = []
        if div_score >= 70:
            strengths.append("Robust multi-sector asset distribution buffers portfolio.")
        if top_1 <= 0.20:
            strengths.append("No single asset dominates portfolio risk profile.")
        if sharpe >= 1.0:
            strengths.append(f"Strong risk-adjusted excess returns (Sharpe {sharpe:.2f}).")
        if max_dd <= 0.15:
            strengths.append(f"Low peak-to-trough historical drawdown ({max_dd*100:.1f}%).")

        if top_1 > 0.25:
            risks.append(f"High single-stock concentration: largest asset exceeds {top_1*100:.1f}%.")
        if max_dd > 0.25:
            risks.append(f"Significant historical drawdown experienced ({max_dd*100:.1f}%).")
        if sharpe < 0.5:
            risks.append("Subdued risk-adjusted return relative to risk-free benchmark.")
        if len(holdings) < 4:
            risks.append("Low overall asset count increases vulnerability to firm-specific shocks.")

        return HealthScoreResponse(
            portfolio_id=portfolio.id,
            overall_score=overall,
            rating=rating,
            status="VALID",
            components=components,
            key_strengths=strengths or ["Active portfolio tracking."],
            key_risks=risks or ["Normal market volatility expected."],
            disclaimer=DISCLAIMER,
        )


_health_engine: Optional[HealthScoreEngine] = None


def get_health_score_engine() -> HealthScoreEngine:
    global _health_engine
    if _health_engine is None:
        _health_engine = HealthScoreEngine()
    return _health_engine
