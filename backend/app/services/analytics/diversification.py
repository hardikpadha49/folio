"""
FolioPulse AI — Diversification Index Engine

Calculates a transparent 0–100 Diversification Index across 5 measurable dimensions:
1. Holdings Breadth (Effective N Holdings)
2. Concentration Balance (Herfindahl-Hirschman Index)
3. Asset-Class Multi-Pillar Entropy
4. Sector Distribution Entropy
5. Correlation-Adjusted Diversification Ratio (DR = sum(w_i * sigma_i) / sigma_p)

Provides transparent component scoring, rating, and plain-language explanation.
"""
import logging
import math
from typing import Dict, List, Optional
import numpy as np

from app.models.user import Portfolio, Holding
from app.schemas.analytics import (
    DiversificationResponse,
    DiversificationComponent,
)
from app.services.analytics.math_utils import (
    calculate_hhi,
    calculate_effective_n,
    calculate_shannon_entropy,
)
from app.services.analytics.risk import RiskEngine, get_risk_engine
from app.services.market_data.base import HistoricalData

logger = logging.getLogger(__name__)


class DiversificationEngine:
    """Computes transparent portfolio diversification scores."""

    def __init__(self, risk_engine: Optional[RiskEngine] = None):
        self.risk_engine = risk_engine or get_risk_engine()

    async def calculate_diversification(
        self,
        portfolio: Portfolio,
        custom_history: Optional[Dict[str, HistoricalData]] = None,
    ) -> DiversificationResponse:
        holdings: List[Holding] = portfolio.holdings or []

        if not holdings:
            return DiversificationResponse(
                portfolio_id=portfolio.id,
                score=0.0,
                rating="Highly Concentrated",
                components=[
                    DiversificationComponent(
                        dimension="Portfolio Empty",
                        score=0.0,
                        weight=1.0,
                        metric_value="0 holdings",
                        description="Add holdings to establish diversification.",
                    )
                ],
                explanation="Your portfolio contains no holdings. Add assets across multiple sectors to build diversification.",
            )

        # 1. Weights based on holding cost basis
        cost_map = {h.ticker: h.quantity * h.average_cost for h in holdings}
        total_cost = sum(cost_map.values()) if cost_map else 1.0
        weights = [c / total_cost for c in cost_map.values()]

        # 2. Component 1: Breadth (Effective N) - 25% weight
        hhi = calculate_hhi(weights)
        eff_n = calculate_effective_n(weights)
        # Optimal benchmark breadth: 10 well-allocated positions
        breadth_score = min(100.0, max(0.0, (eff_n / 10.0) * 100.0))

        # 3. Component 2: Concentration Balance (HHI) - 25% weight
        # HHI=1.0 (single asset) -> 0 score; HHI=0.1 (10 equal) -> 100 score
        conc_score = max(0.0, min(100.0, (1.0 - hhi) * 111.1))

        # 4. Component 3: Asset Class Entropy - 20% weight
        asset_class_costs: Dict[str, float] = {}
        for h in holdings:
            ac = h.asset_class.lower()
            asset_class_costs[ac] = asset_class_costs.get(ac, 0.0) + (h.quantity * h.average_cost)
        ac_weights = [c / total_cost for c in asset_class_costs.values()]
        ac_entropy = calculate_shannon_entropy(ac_weights)
        # Max entropy for 4 typical classes (equity, debt, commodity, cash) is ln(4) ≈ 1.386
        ac_score = min(100.0, (ac_entropy / 1.386) * 100.0) if ac_entropy > 0 else 20.0

        # 5. Component 4: Sector Entropy - 15% weight
        sector_costs: Dict[str, float] = {}
        for h in holdings:
            sec = (h.sector or "Unclassified").strip()
            sector_costs[sec] = sector_costs.get(sec, 0.0) + (h.quantity * h.average_cost)
        sec_weights = [c / total_cost for c in sector_costs.values()]
        sec_entropy = calculate_shannon_entropy(sec_weights)
        # Max entropy for 6 balanced sectors is ln(6) ≈ 1.792
        sec_score = min(100.0, (sec_entropy / 1.792) * 100.0) if sec_entropy > 0 else 15.0

        # 6. Component 5: Correlation-Adjusted Diversification Ratio - 15% weight
        # DR = sum(w_i * sigma_i) / sigma_p
        dr_score = 50.0  # Default neutral
        dr_val = 1.0
        try:
            risk_metrics = await self.risk_engine.calculate_risk(
                portfolio, period="1y", custom_history=custom_history
            )
            if risk_metrics.observation_count >= 5 and risk_metrics.annualized_volatility > 1e-4:
                sum_weighted_vols = sum(
                    rc.weight * rc.annualized_volatility for rc in risk_metrics.risk_contributions
                )
                dr_val = sum_weighted_vols / risk_metrics.annualized_volatility
                # DR=1.0 (perfect correlation) -> 20 pts; DR=1.3+ (30% risk reduction) -> 100 pts
                dr_score = max(0.0, min(100.0, ((dr_val - 1.0) / 0.3) * 80.0 + 20.0))
        except Exception as e:
            logger.debug("Could not calculate DR for diversification score: %s", e)

        # Weighted aggregate score
        weights_components = [0.25, 0.25, 0.20, 0.15, 0.15]
        scores = [breadth_score, conc_score, ac_score, sec_score, dr_score]
        overall_score = round(sum(w * s for w, s in zip(weights_components, scores)), 1)

        # Rating label
        if overall_score >= 80:
            rating = "High Diversification"
        elif overall_score >= 60:
            rating = "Moderate Diversification"
        elif overall_score >= 40:
            rating = "Concentrated"
        else:
            rating = "Highly Concentrated"

        components = [
            DiversificationComponent(
                dimension="Holdings Breadth",
                score=round(breadth_score, 1),
                weight=0.25,
                metric_value=f"Effective N: {eff_n:.1f} / {len(holdings)} holdings",
                description="Measures breadth beyond nominal holding count to penalize nominal diversification dominated by 1-2 stocks.",
            ),
            DiversificationComponent(
                dimension="Concentration Balance",
                score=round(conc_score, 1),
                weight=0.25,
                metric_value=f"HHI: {hhi:.4f}",
                description="Inverse Herfindahl-Hirschman Index. Lower weight inequality scores higher.",
            ),
            DiversificationComponent(
                dimension="Asset Class Pillars",
                score=round(ac_score, 1),
                weight=0.20,
                metric_value=f"{len(asset_class_costs)} asset class(es)",
                description="Distribution across equities, fixed income, commodities, and cash.",
            ),
            DiversificationComponent(
                dimension="Sector Spread",
                score=round(sec_score, 1),
                weight=0.15,
                metric_value=f"{len(sector_costs)} sector(s)",
                description="Entropy across economic sectors to prevent cluster risk in a single industry.",
            ),
            DiversificationComponent(
                dimension="Correlation Benefit",
                score=round(dr_score, 1),
                weight=0.15,
                metric_value=f"Diversification Ratio: {dr_val:.2f}x",
                description="Ratio of weighted individual asset risks to combined portfolio risk. Values above 1.0 indicate non-aligned volatility buffers.",
            ),
        ]

        # Plain language explanation
        if overall_score >= 75:
            explanation = (
                f"Your portfolio demonstrates strong multi-pillar diversification (Score: {overall_score}/100) with an effective count of {eff_n:.1f} holdings. "
                "Assets are spread well across categories, buffering against individual market downturns."
            )
        elif overall_score >= 50:
            top_holding = sorted(holdings, key=lambda h: h.quantity * h.average_cost, reverse=True)[0]
            top_w = (top_holding.quantity * top_holding.average_cost) / total_cost * 100
            explanation = (
                f"Your portfolio has moderate diversification (Score: {overall_score}/100). "
                f"Noticeable concentration remains in {top_holding.ticker} ({top_w:.1f}%). "
                "Consider expanding into uncorrelated sectors or fixed income pillars to improve stability."
            )
        else:
            explanation = (
                f"High concentration detected (Score: {overall_score}/100). "
                "Capital is clustered in very few positions or a single sector, increasing vulnerability to company-specific shocks."
            )

        return DiversificationResponse(
            portfolio_id=portfolio.id,
            score=overall_score,
            rating=rating,
            components=components,
            explanation=explanation,
        )


_div_engine: Optional[DiversificationEngine] = None


def get_diversification_engine() -> DiversificationEngine:
    global _div_engine
    if _div_engine is None:
        _div_engine = DiversificationEngine()
    return _div_engine
