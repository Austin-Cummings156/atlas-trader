"""Fundamental analysis helpers for swing and position research."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


class FundamentalSignal(StrEnum):
    """Directional signal for one fundamental category."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class FundamentalRating(StrEnum):
    """Overall fundamental quality rating."""

    STRONG = "strong"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    WEAK = "weak"
    UNKNOWN = "unknown"


class ValuationLevel(StrEnum):
    """Valuation context from price-to-earnings ratio."""

    LOW = "low"
    FAIR = "fair"
    HIGH = "high"
    UNKNOWN = "unknown"


class EarningsTrend(StrEnum):
    """Recent quarterly earnings direction."""

    IMPROVING = "improving"
    FLAT = "flat"
    DECLINING = "declining"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FundamentalAnalysisSettings:
    """Tunable thresholds used by fundamental analysis."""

    strong_growth_rate: float = 0.15
    positive_growth_rate: float = 0.05
    weak_growth_rate: float = 0.0
    strong_performance_rate: float = 0.20
    positive_performance_rate: float = 0.05
    weak_performance_rate: float = 0.0
    low_pe_ratio: float = 15.0
    high_pe_ratio: float = 30.0
    max_healthy_debt_to_equity: float = 1.0
    max_elevated_debt_to_equity: float = 2.0
    healthy_profit_margin: float = 0.10
    healthy_return_on_equity: float = 0.12
    flat_earnings_tolerance_ratio: float = 0.03
    min_quarters_for_trend: int = 3
    strong_rating_score: float = 0.60
    positive_rating_score: float = 0.20
    weak_rating_score: float = -0.20

    def __post_init__(self) -> None:
        """Validate fundamental-analysis thresholds."""
        if not (self.weak_growth_rate <= self.positive_growth_rate <= self.strong_growth_rate):
            raise ValueError("growth thresholds must satisfy weak <= positive <= strong.")
        if not (
            self.weak_performance_rate
            <= self.positive_performance_rate
            <= self.strong_performance_rate
        ):
            raise ValueError("performance thresholds must satisfy weak <= positive <= strong.")
        if not 0 < self.low_pe_ratio <= self.high_pe_ratio:
            raise ValueError("P/E thresholds must satisfy 0 < low_pe_ratio <= high_pe_ratio.")
        if not 0 <= self.max_healthy_debt_to_equity <= self.max_elevated_debt_to_equity:
            raise ValueError(
                "debt thresholds must satisfy "
                "0 <= max_healthy_debt_to_equity <= max_elevated_debt_to_equity."
            )
        if self.min_quarters_for_trend <= 1:
            raise ValueError("min_quarters_for_trend must be greater than one.")
        if self.flat_earnings_tolerance_ratio < 0:
            raise ValueError("flat_earnings_tolerance_ratio cannot be negative.")
        if not (self.weak_rating_score <= self.positive_rating_score <= self.strong_rating_score):
            raise ValueError("rating thresholds must satisfy weak <= positive <= strong.")


DEFAULT_FUNDAMENTAL_ANALYSIS_SETTINGS = FundamentalAnalysisSettings()


@dataclass(frozen=True)
class FundamentalMetrics:
    """Raw company-level fundamental metrics for one symbol."""

    symbol: str
    annual_growth_rate: float | None = None
    five_year_performance: float | None = None
    one_year_performance: float | None = None
    quarterly_eps: Sequence[float] = field(default_factory=tuple)
    pe_ratio: float | None = None
    eps_growth: float | None = None
    revenue_growth: float | None = None
    debt_to_equity: float | None = None
    profit_margin: float | None = None
    return_on_equity: float | None = None

    def __post_init__(self) -> None:
        """Validate supplied fundamental metrics."""
        if not self.symbol.strip():
            raise ValueError("symbol must not be blank.")

        _validate_optional_finite(self.annual_growth_rate, "annual_growth_rate")
        _validate_optional_finite(self.five_year_performance, "five_year_performance")
        _validate_optional_finite(self.one_year_performance, "one_year_performance")
        _validate_optional_finite(self.eps_growth, "eps_growth")
        _validate_optional_finite(self.revenue_growth, "revenue_growth")
        _validate_optional_finite(self.profit_margin, "profit_margin")
        _validate_optional_finite(self.return_on_equity, "return_on_equity")
        _validate_optional_positive(self.pe_ratio, "pe_ratio")
        _validate_optional_non_negative(self.debt_to_equity, "debt_to_equity")

        if not all(isfinite(value) for value in self.quarterly_eps):
            raise ValueError("quarterly_eps values must be finite numbers.")


@dataclass(frozen=True)
class FundamentalAnalysis:
    """Classified fundamental context for swing and position research."""

    metrics: FundamentalMetrics
    growth_signal: FundamentalSignal
    performance_signal: FundamentalSignal
    earnings_trend: EarningsTrend
    earnings_signal: FundamentalSignal
    valuation_level: ValuationLevel
    valuation_signal: FundamentalSignal
    debt_signal: FundamentalSignal
    profitability_signal: FundamentalSignal
    score: float | None
    data_quality: float
    rating: FundamentalRating

    @property
    def symbol(self) -> str:
        """Return the analyzed symbol."""
        return self.metrics.symbol


def analyze_fundamentals(
    metrics: FundamentalMetrics,
    *,
    settings: FundamentalAnalysisSettings = DEFAULT_FUNDAMENTAL_ANALYSIS_SETTINGS,
) -> FundamentalAnalysis:
    """Analyze supplied fundamental metrics without fetching external data."""
    growth_signal = _combined_signal(
        [
            _classify_rate(metrics.annual_growth_rate, settings, category="growth"),
            _classify_rate(metrics.eps_growth, settings, category="growth"),
            _classify_rate(metrics.revenue_growth, settings, category="growth"),
        ]
    )
    performance_signal = _combined_signal(
        [
            _classify_rate(metrics.five_year_performance, settings, category="performance"),
            _classify_rate(metrics.one_year_performance, settings, category="performance"),
        ]
    )
    earnings_trend = classify_earnings_trend(metrics.quarterly_eps, settings=settings)
    earnings_signal = _signal_for_earnings_trend(earnings_trend)
    valuation_level = classify_valuation(metrics.pe_ratio, settings=settings)
    valuation_signal = _signal_for_valuation(valuation_level)
    debt_signal = classify_debt(metrics.debt_to_equity, settings=settings)
    profitability_signal = classify_profitability(
        profit_margin=metrics.profit_margin,
        return_on_equity=metrics.return_on_equity,
        settings=settings,
    )
    category_signals = [
        growth_signal,
        performance_signal,
        earnings_signal,
        valuation_signal,
        debt_signal,
        profitability_signal,
    ]
    score = _score_signals(category_signals)

    return FundamentalAnalysis(
        metrics=metrics,
        growth_signal=growth_signal,
        performance_signal=performance_signal,
        earnings_trend=earnings_trend,
        earnings_signal=earnings_signal,
        valuation_level=valuation_level,
        valuation_signal=valuation_signal,
        debt_signal=debt_signal,
        profitability_signal=profitability_signal,
        score=score,
        data_quality=_data_quality(category_signals),
        rating=_rating_for_score(score, settings),
    )


def classify_valuation(
    pe_ratio: float | None,
    *,
    settings: FundamentalAnalysisSettings = DEFAULT_FUNDAMENTAL_ANALYSIS_SETTINGS,
) -> ValuationLevel:
    """Classify valuation from price-to-earnings ratio."""
    if pe_ratio is None:
        return ValuationLevel.UNKNOWN
    if pe_ratio <= settings.low_pe_ratio:
        return ValuationLevel.LOW
    if pe_ratio <= settings.high_pe_ratio:
        return ValuationLevel.FAIR
    return ValuationLevel.HIGH


def classify_debt(
    debt_to_equity: float | None,
    *,
    settings: FundamentalAnalysisSettings = DEFAULT_FUNDAMENTAL_ANALYSIS_SETTINGS,
) -> FundamentalSignal:
    """Classify debt load from debt-to-equity ratio."""
    if debt_to_equity is None:
        return FundamentalSignal.UNKNOWN
    if debt_to_equity <= settings.max_healthy_debt_to_equity:
        return FundamentalSignal.POSITIVE
    if debt_to_equity <= settings.max_elevated_debt_to_equity:
        return FundamentalSignal.NEUTRAL
    return FundamentalSignal.NEGATIVE


def classify_profitability(
    *,
    profit_margin: float | None,
    return_on_equity: float | None,
    settings: FundamentalAnalysisSettings = DEFAULT_FUNDAMENTAL_ANALYSIS_SETTINGS,
) -> FundamentalSignal:
    """Classify profitability from margin and return on equity."""
    signals = [
        _classify_profit_metric(profit_margin, settings.healthy_profit_margin),
        _classify_profit_metric(return_on_equity, settings.healthy_return_on_equity),
    ]
    return _combined_signal(signals)


def classify_earnings_trend(
    quarterly_eps: Sequence[float],
    *,
    settings: FundamentalAnalysisSettings = DEFAULT_FUNDAMENTAL_ANALYSIS_SETTINGS,
) -> EarningsTrend:
    """Classify recent quarterly EPS trend."""
    if len(quarterly_eps) < settings.min_quarters_for_trend:
        return EarningsTrend.UNKNOWN

    recent_eps = list(quarterly_eps[-settings.min_quarters_for_trend :])
    changes = [
        _classify_change(previous, current, settings.flat_earnings_tolerance_ratio)
        for previous, current in zip(recent_eps, recent_eps[1:], strict=False)
    ]

    if all(change == FundamentalSignal.POSITIVE for change in changes):
        return EarningsTrend.IMPROVING
    if all(change == FundamentalSignal.NEGATIVE for change in changes):
        return EarningsTrend.DECLINING
    if all(change == FundamentalSignal.NEUTRAL for change in changes):
        return EarningsTrend.FLAT
    return EarningsTrend.MIXED


def _validate_optional_finite(value: float | None, name: str) -> None:
    if value is not None and not isfinite(value):
        raise ValueError(f"{name} must be a finite number.")


def _validate_optional_positive(value: float | None, name: str) -> None:
    _validate_optional_finite(value, name)
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _validate_optional_non_negative(value: float | None, name: str) -> None:
    _validate_optional_finite(value, name)
    if value is not None and value < 0:
        raise ValueError(f"{name} cannot be negative.")


def _classify_rate(
    rate: float | None,
    settings: FundamentalAnalysisSettings,
    *,
    category: str,
) -> FundamentalSignal:
    if rate is None:
        return FundamentalSignal.UNKNOWN

    if category == "growth":
        positive_rate = settings.positive_growth_rate
        weak_rate = settings.weak_growth_rate
    else:
        positive_rate = settings.positive_performance_rate
        weak_rate = settings.weak_performance_rate

    if rate >= positive_rate:
        return FundamentalSignal.POSITIVE
    if rate >= weak_rate:
        return FundamentalSignal.NEUTRAL
    return FundamentalSignal.NEGATIVE


def _classify_profit_metric(
    value: float | None,
    healthy_threshold: float,
) -> FundamentalSignal:
    if value is None:
        return FundamentalSignal.UNKNOWN
    if value >= healthy_threshold:
        return FundamentalSignal.POSITIVE
    if value >= 0:
        return FundamentalSignal.NEUTRAL
    return FundamentalSignal.NEGATIVE


def _classify_change(
    previous: float,
    current: float,
    flat_tolerance_ratio: float,
) -> FundamentalSignal:
    if previous == 0:
        if current == 0:
            return FundamentalSignal.NEUTRAL
        return FundamentalSignal.POSITIVE if current > 0 else FundamentalSignal.NEGATIVE

    change_ratio = (current - previous) / abs(previous)
    if abs(change_ratio) <= flat_tolerance_ratio:
        return FundamentalSignal.NEUTRAL
    if change_ratio > 0:
        return FundamentalSignal.POSITIVE
    return FundamentalSignal.NEGATIVE


def _signal_for_earnings_trend(earnings_trend: EarningsTrend) -> FundamentalSignal:
    if earnings_trend == EarningsTrend.IMPROVING:
        return FundamentalSignal.POSITIVE
    if earnings_trend == EarningsTrend.DECLINING:
        return FundamentalSignal.NEGATIVE
    if earnings_trend in {EarningsTrend.FLAT, EarningsTrend.MIXED}:
        return FundamentalSignal.NEUTRAL
    return FundamentalSignal.UNKNOWN


def _signal_for_valuation(valuation_level: ValuationLevel) -> FundamentalSignal:
    if valuation_level in {ValuationLevel.LOW, ValuationLevel.FAIR}:
        return FundamentalSignal.POSITIVE
    if valuation_level == ValuationLevel.HIGH:
        return FundamentalSignal.NEGATIVE
    return FundamentalSignal.UNKNOWN


def _combined_signal(signals: Sequence[FundamentalSignal]) -> FundamentalSignal:
    known_scores = [
        _score_for_signal(signal) for signal in signals if signal != FundamentalSignal.UNKNOWN
    ]
    if not known_scores:
        return FundamentalSignal.UNKNOWN

    average_score = sum(known_scores) / len(known_scores)
    if average_score > 0:
        return FundamentalSignal.POSITIVE
    if average_score < 0:
        return FundamentalSignal.NEGATIVE
    return FundamentalSignal.NEUTRAL


def _score_signals(signals: Sequence[FundamentalSignal]) -> float | None:
    known_scores = [
        _score_for_signal(signal) for signal in signals if signal != FundamentalSignal.UNKNOWN
    ]
    if not known_scores:
        return None

    return round(sum(known_scores) / len(known_scores), 4)


def _score_for_signal(signal: FundamentalSignal) -> int:
    if signal == FundamentalSignal.POSITIVE:
        return 1
    if signal == FundamentalSignal.NEGATIVE:
        return -1
    return 0


def _data_quality(signals: Sequence[FundamentalSignal]) -> float:
    if not signals:
        return 0

    known_count = sum(signal != FundamentalSignal.UNKNOWN for signal in signals)
    return round(known_count / len(signals), 4)


def _rating_for_score(
    score: float | None,
    settings: FundamentalAnalysisSettings,
) -> FundamentalRating:
    if score is None:
        return FundamentalRating.UNKNOWN
    if score >= settings.strong_rating_score:
        return FundamentalRating.STRONG
    if score >= settings.positive_rating_score:
        return FundamentalRating.POSITIVE
    if score > settings.weak_rating_score:
        return FundamentalRating.NEUTRAL
    return FundamentalRating.WEAK
