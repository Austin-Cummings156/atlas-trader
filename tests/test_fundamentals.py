"""Tests for fundamental analysis helpers."""

import math

import pandas as pd
import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.fundamentals import (
    EarningsTrend,
    FundamentalAnalysisSettings,
    FundamentalMetrics,
    FundamentalRating,
    FundamentalSignal,
    ValuationLevel,
    analyze_fundamentals,
    analyze_symbol_fundamentals,
    classify_debt,
    classify_earnings_trend,
    classify_profitability,
    classify_valuation,
    fetch_fundamental_metrics,
)


class FakeTicker:
    info = {
        "trailingPE": 22.0,
        "earningsQuarterlyGrowth": 0.16,
        "revenueGrowth": 0.10,
        "debtToEquity": 70.0,
        "profitMargins": 0.22,
        "returnOnEquity": 0.35,
    }
    financials = pd.DataFrame(
        {
            pd.Timestamp("2021-12-31"): [100.0],
            pd.Timestamp("2022-12-31"): [116.0],
            pd.Timestamp("2023-12-31"): [135.0],
        },
        index=["Total Revenue"],
    )
    quarterly_income_stmt = pd.DataFrame(
        {
            pd.Timestamp("2023-03-31"): [1.00],
            pd.Timestamp("2023-06-30"): [1.08],
            pd.Timestamp("2023-09-30"): [1.20],
            pd.Timestamp("2023-12-31"): [1.35],
        },
        index=["Diluted EPS"],
    )

    def history(self, *, period: str, interval: str, auto_adjust: bool) -> pd.DataFrame:
        if period == "5y":
            closes = [100.0, 180.0]
        else:
            closes = [100.0, 125.0]

        return pd.DataFrame({"Close": closes})


def test_fundamental_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.FundamentalMetrics is FundamentalMetrics
    assert analysis_api.FundamentalAnalysisSettings is FundamentalAnalysisSettings
    assert analysis_api.analyze_fundamentals is analyze_fundamentals
    assert analysis_api.analyze_symbol_fundamentals is analyze_symbol_fundamentals
    assert analysis_api.fetch_fundamental_metrics is fetch_fundamental_metrics
    assert analysis_api.FundamentalRating is FundamentalRating


def test_fetch_fundamental_metrics_loads_provider_data() -> None:
    metrics = fetch_fundamental_metrics(" aapl ", ticker_factory=lambda symbol: FakeTicker())

    assert metrics.symbol == "AAPL"
    assert metrics.annual_growth_rate == pytest.approx(0.1619, abs=0.0001)
    assert metrics.five_year_performance == pytest.approx(0.80)
    assert metrics.one_year_performance == pytest.approx(0.25)
    assert metrics.quarterly_eps == pytest.approx((1.00, 1.08, 1.20, 1.35))
    assert metrics.pe_ratio == pytest.approx(22)
    assert metrics.eps_growth == pytest.approx(0.16)
    assert metrics.revenue_growth == pytest.approx(0.10)
    assert metrics.debt_to_equity == pytest.approx(0.70)
    assert metrics.profit_margin == pytest.approx(0.22)
    assert metrics.return_on_equity == pytest.approx(0.35)


def test_analyze_symbol_fundamentals_fetches_and_scores_provider_data() -> None:
    analysis = analyze_symbol_fundamentals("AAPL", ticker_factory=lambda symbol: FakeTicker())

    assert analysis.symbol == "AAPL"
    assert analysis.rating == FundamentalRating.STRONG
    assert analysis.data_quality == pytest.approx(1)


def test_analyze_fundamentals_rates_strong_company_context() -> None:
    metrics = FundamentalMetrics(
        symbol="AAPL",
        annual_growth_rate=0.18,
        five_year_performance=0.80,
        one_year_performance=0.25,
        quarterly_eps=[1.00, 1.08, 1.20, 1.35],
        pe_ratio=22,
        eps_growth=0.16,
        revenue_growth=0.10,
        debt_to_equity=0.70,
        profit_margin=0.22,
        return_on_equity=0.35,
    )

    analysis = analyze_fundamentals(metrics)

    assert analysis.symbol == "AAPL"
    assert analysis.growth_signal == FundamentalSignal.POSITIVE
    assert analysis.performance_signal == FundamentalSignal.POSITIVE
    assert analysis.earnings_trend == EarningsTrend.IMPROVING
    assert analysis.valuation_level == ValuationLevel.FAIR
    assert analysis.debt_signal == FundamentalSignal.POSITIVE
    assert analysis.profitability_signal == FundamentalSignal.POSITIVE
    assert analysis.rating == FundamentalRating.STRONG
    assert analysis.score == pytest.approx(1)
    assert analysis.data_quality == pytest.approx(1)


def test_analyze_fundamentals_rates_weak_company_context() -> None:
    metrics = FundamentalMetrics(
        symbol="WEAK",
        annual_growth_rate=-0.05,
        five_year_performance=-0.30,
        one_year_performance=-0.15,
        quarterly_eps=[1.30, 1.10, 1.00, 0.80],
        pe_ratio=45,
        eps_growth=-0.10,
        revenue_growth=-0.02,
        debt_to_equity=3.0,
        profit_margin=-0.03,
        return_on_equity=-0.04,
    )

    analysis = analyze_fundamentals(metrics)

    assert analysis.growth_signal == FundamentalSignal.NEGATIVE
    assert analysis.performance_signal == FundamentalSignal.NEGATIVE
    assert analysis.earnings_trend == EarningsTrend.DECLINING
    assert analysis.valuation_level == ValuationLevel.HIGH
    assert analysis.debt_signal == FundamentalSignal.NEGATIVE
    assert analysis.profitability_signal == FundamentalSignal.NEGATIVE
    assert analysis.rating == FundamentalRating.WEAK
    assert analysis.score == pytest.approx(-1)


def test_analyze_fundamentals_handles_partial_data() -> None:
    metrics = FundamentalMetrics(
        symbol="PARTIAL",
        pe_ratio=12,
        debt_to_equity=1.5,
    )

    analysis = analyze_fundamentals(metrics)

    assert analysis.growth_signal == FundamentalSignal.UNKNOWN
    assert analysis.performance_signal == FundamentalSignal.UNKNOWN
    assert analysis.earnings_trend == EarningsTrend.UNKNOWN
    assert analysis.valuation_level == ValuationLevel.LOW
    assert analysis.valuation_signal == FundamentalSignal.POSITIVE
    assert analysis.debt_signal == FundamentalSignal.NEUTRAL
    assert analysis.rating == FundamentalRating.POSITIVE
    assert analysis.data_quality == pytest.approx(2 / 6, abs=0.0001)


def test_standalone_fundamental_classifiers() -> None:
    assert classify_valuation(None) == ValuationLevel.UNKNOWN
    assert classify_valuation(10) == ValuationLevel.LOW
    assert classify_valuation(20) == ValuationLevel.FAIR
    assert classify_valuation(40) == ValuationLevel.HIGH

    assert classify_debt(None) == FundamentalSignal.UNKNOWN
    assert classify_debt(0.5) == FundamentalSignal.POSITIVE
    assert classify_debt(1.5) == FundamentalSignal.NEUTRAL
    assert classify_debt(2.5) == FundamentalSignal.NEGATIVE

    assert classify_profitability(profit_margin=0.2, return_on_equity=0.2) == (
        FundamentalSignal.POSITIVE
    )
    assert classify_profitability(profit_margin=-0.1, return_on_equity=-0.1) == (
        FundamentalSignal.NEGATIVE
    )


def test_earnings_trend_classifies_improving_flat_declining_and_mixed() -> None:
    settings = FundamentalAnalysisSettings(flat_earnings_tolerance_ratio=0.03)

    assert classify_earnings_trend([1.0, 1.2, 1.4], settings=settings) == (EarningsTrend.IMPROVING)
    assert classify_earnings_trend([1.0, 1.01, 1.02], settings=settings) == EarningsTrend.FLAT
    assert classify_earnings_trend([1.4, 1.2, 1.0], settings=settings) == (EarningsTrend.DECLINING)
    assert classify_earnings_trend([1.0, 1.2, 1.1], settings=settings) == EarningsTrend.MIXED
    assert classify_earnings_trend([1.0, 1.2], settings=settings) == EarningsTrend.UNKNOWN


def test_fundamental_analysis_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="symbol"):
        FundamentalMetrics(symbol="")

    with pytest.raises(ValueError, match="pe_ratio"):
        FundamentalMetrics(symbol="BAD", pe_ratio=0)

    with pytest.raises(ValueError, match="debt_to_equity"):
        FundamentalMetrics(symbol="BAD", debt_to_equity=-1)

    with pytest.raises(ValueError, match="quarterly_eps"):
        FundamentalMetrics(symbol="BAD", quarterly_eps=[1.0, math.inf])

    with pytest.raises(ValueError, match="growth thresholds"):
        FundamentalAnalysisSettings(
            weak_growth_rate=0.10,
            positive_growth_rate=0.05,
        )
