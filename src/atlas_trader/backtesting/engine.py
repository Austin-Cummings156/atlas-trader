"""Historical market-reading validation helpers."""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_trader.analysis.moving_averages import (
    MovingAverageLevel,
    MovingAverageReportContext,
    analyze_moving_average_context,
)
from atlas_trader.analysis.ranges import (
    BreakoutDirection,
    SidewaysMarketAnalysis,
    SidewaysMarketType,
    analyze_sideways_market,
)
from atlas_trader.analysis.support_resistance import (
    LevelPosition,
    PriceLevel,
    SupportResistanceAnalysis,
    analyze_support_resistance,
)
from atlas_trader.analysis.trend_evidence import (
    TrendEvidenceContext,
    analyze_trend_evidence,
)
from atlas_trader.analysis.trend_health import (
    TrendHealthContext,
    analyze_trend_health,
)
from atlas_trader.analysis.trends import (
    SwingPoint,
    TrendAnalysis,
    TrendDirection,
    analyze_trend,
)
from atlas_trader.analysis.volatility import (
    VolatilityContext,
    VolatilityLevel,
    analyze_volatility,
)
from atlas_trader.analysis.volume import (
    BreakoutVolumeContext,
    RelativeVolumeLevel,
    VolumeContext,
    analyze_volume,
)
from atlas_trader.data.models import Candle


class HistoricalReadBias(StrEnum):
    """Directional market read for one historical snapshot."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class HistoricalAuditReason(StrEnum):
    """Reason a historical snapshot is worth reviewing."""

    TREND_CHANGED = "trend_changed"
    MARKET_TYPE_CHANGED = "market_type_changed"
    BIAS_CHANGED = "bias_changed"
    BREAKOUT = "breakout"
    HIGH_RELATIVE_VOLUME = "high_relative_volume"
    CONFIRMED_BREAKOUT_VOLUME = "confirmed_breakout_volume"
    NEAR_SUPPORT = "near_support"
    NEAR_RESISTANCE = "near_resistance"


@dataclass(frozen=True)
class HistoricalReadSettings:
    """Tunable settings for historical market-reading validation."""

    lookback: int = 60
    step: int = 1
    indicator_warmup_lookback: int = 250
    trend_strength: int | None = None
    support_resistance_strength: int | None = None
    volume_average_period: int | None = None
    min_window: int | None = None

    def __post_init__(self) -> None:
        """Validate historical-read settings."""
        if self.lookback <= 1:
            raise ValueError("lookback must be greater than one.")
        if self.step <= 0:
            raise ValueError("step must be greater than zero.")
        if self.indicator_warmup_lookback <= 1:
            raise ValueError("indicator_warmup_lookback must be greater than one.")
        if self.trend_strength is not None and self.trend_strength <= 0:
            raise ValueError("trend_strength must be greater than zero.")
        if self.support_resistance_strength is not None and self.support_resistance_strength <= 0:
            raise ValueError("support_resistance_strength must be greater than zero.")
        if self.volume_average_period is not None and self.volume_average_period <= 0:
            raise ValueError("volume_average_period must be greater than zero.")
        if self.min_window is not None and self.min_window <= 1:
            raise ValueError("min_window must be greater than one.")
        if self.min_window is not None and self.min_window > self.lookback:
            raise ValueError("min_window cannot be greater than lookback.")


DEFAULT_HISTORICAL_READ_SETTINGS = HistoricalReadSettings()


@dataclass(frozen=True)
class HistoricalReadSnapshot:
    """Market reader output at one point in historical time."""

    index: int
    candle: Candle
    window_size: int
    indicator_window_size: int
    trend: TrendAnalysis
    sideways_market: SidewaysMarketAnalysis
    support_resistance: SupportResistanceAnalysis
    volume: VolumeContext
    volatility: VolatilityContext
    moving_averages: MovingAverageReportContext
    trend_health: TrendHealthContext
    trend_evidence: TrendEvidenceContext
    bias: HistoricalReadBias

    @property
    def close(self) -> float:
        """Return the snapshot close price."""
        return self.candle.close

    def to_debug_report(
        self,
        *,
        timeframe: str | None = None,
        reasons: Sequence[HistoricalAuditReason] | None = None,
    ) -> dict[str, object]:
        """Return a stable, machine-readable report of this market read."""
        nearest_support = self.support_resistance.nearest_support
        nearest_resistance = self.support_resistance.nearest_resistance

        report = {
            "symbol": self.candle.symbol,
            "timeframe": timeframe,
            "snapshot_index": self.index,
            "candle_timestamp": self.candle.timestamp.isoformat(),
            "candle_date": self.candle.timestamp.date().isoformat(),
            "window_size": self.window_size,
            "indicator_window_size": self.indicator_window_size,
            "latest_close": self.close,
            "bias": self.bias.value,
            "trend_direction": self.trend.direction.value,
            "trend_confidence": self.trend.confidence,
            "market_type": self.sideways_market.market_type.value,
            "market_confidence": self.sideways_market.confidence,
            "latest_swing_high": _swing_point_report(self.trend.latest_swing_high),
            "latest_swing_low": _swing_point_report(self.trend.latest_swing_low),
            "recent_swing_high": _swing_point_report(self.trend.latest_swing_high),
            "recent_swing_low": _swing_point_report(self.trend.latest_swing_low),
            "swing_highs": _swing_point_reports(self.trend.swing_highs),
            "swing_lows": _swing_point_reports(self.trend.swing_lows),
            "confirmed_swing_high_count": (self.trend_evidence.confirmed_swing_high_count),
            "confirmed_swing_low_count": self.trend_evidence.confirmed_swing_low_count,
            "higher_high_count": self.trend.higher_high_count,
            "higher_low_count": self.trend.higher_low_count,
            "lower_high_count": self.trend.lower_high_count,
            "lower_low_count": self.trend.lower_low_count,
            "equal_high_count": self.trend.equal_high_count,
            "equal_low_count": self.trend.equal_low_count,
            "higher_high_ratio": self.trend_evidence.higher_high_ratio,
            "higher_low_ratio": self.trend_evidence.higher_low_ratio,
            "lower_high_ratio": self.trend_evidence.lower_high_ratio,
            "lower_low_ratio": self.trend_evidence.lower_low_ratio,
            "trend_fallback_reason": (
                self.trend_evidence.trend_fallback_reason.value
                if self.trend_evidence.trend_fallback_reason
                else None
            ),
            "insufficient_swing_structure": (self.trend_evidence.insufficient_swing_structure),
            "trend_candidate": self.trend_evidence.trend_candidate.value,
            "trend_candidate_confidence": (self.trend_evidence.trend_candidate_confidence),
            "trend_candidate_raw_score": self.trend_evidence.trend_candidate_raw_score,
            "trend_candidate_conflict_count": (self.trend_evidence.trend_candidate_conflict_count),
            "trend_candidate_effective_score": (
                self.trend_evidence.trend_candidate_effective_score
            ),
            "trend_candidate_threshold": self.trend_evidence.trend_candidate_threshold,
            "trend_candidate_selected_score": (self.trend_evidence.trend_candidate_selected_score),
            "trend_candidate_blocked_reason": (
                self.trend_evidence.trend_candidate_blocked_reason.value
                if self.trend_evidence.trend_candidate_blocked_reason
                else None
            ),
            "trend_candidate_raw_reasons": self.trend_evidence.trend_candidate_raw_reasons,
            "trend_candidate_reasons": self.trend_evidence.trend_candidate_reasons,
            "trend_candidate_conflicts": self.trend_evidence.trend_candidate_conflicts,
            "messy_trend_candidate": self.trend_evidence.messy_trend_candidate,
            "messy_trend_direction": self.trend_evidence.messy_trend_direction,
            "window_return_pct": self.trend_evidence.window_return_pct,
            "range_upper_bound": self.sideways_market.upper_bound,
            "range_lower_bound": self.sideways_market.lower_bound,
            "range_midpoint": self.sideways_market.midpoint,
            "range_height": self.sideways_market.height,
            "range_height_pct": self.sideways_market.height_pct,
            "close_drift": self.sideways_market.close_drift,
            "close_drift_ratio": self.sideways_market.close_drift_ratio,
            "support_touches": self.sideways_market.support_touches,
            "resistance_touches": self.sideways_market.resistance_touches,
            "breakout_direction": self.sideways_market.breakout_direction.value,
            "nearest_support": _price_level_report(nearest_support),
            "nearest_resistance": _price_level_report(nearest_resistance),
            "nearest_support_price": nearest_support.price if nearest_support else None,
            "nearest_resistance_price": (nearest_resistance.price if nearest_resistance else None),
            "distance_from_support": (
                nearest_support.distance_from_close if nearest_support else None
            ),
            "distance_from_support_pct": (
                nearest_support.distance_from_close_pct if nearest_support else None
            ),
            "distance_from_resistance": (
                nearest_resistance.distance_from_close if nearest_resistance else None
            ),
            "distance_from_resistance_pct": (
                nearest_resistance.distance_from_close_pct if nearest_resistance else None
            ),
            "average_volume": self.volume.average_volume,
            "relative_volume": self.volume.relative_volume,
            "relative_volume_level": self.volume.relative_volume_level.value,
            "volume_trend": self.volume.volume_trend.value,
            "breakout_volume_context": self.volume.breakout_context.value,
            "volatility_level": self.volatility.level.value,
            "average_true_range": self.volatility.average_true_range,
            "average_true_range_pct": self.volatility.average_true_range_pct,
            "average_high_low_range_pct": self.volatility.average_high_low_range_pct,
            "baseline_average_true_range_pct": self.volatility.baseline_average_true_range_pct,
            "recent_vs_baseline_atr_ratio": self.volatility.recent_vs_baseline_atr_ratio,
            "volatility_recent_period": self.volatility.recent_period,
            "volatility_baseline_period": self.volatility.baseline_period,
            "volatility_insufficient_data_reason": self.volatility.insufficient_data_reason,
            "ema_20": self.moving_averages.ema_20.value,
            "ema_50": self.moving_averages.ema_50.value,
            "ema_200": self.moving_averages.ema_200.value,
            "price_vs_ema_20": self.moving_averages.ema_20.position.value,
            "price_vs_ema_50": self.moving_averages.ema_50.position.value,
            "price_vs_ema_200": self.moving_averages.ema_200.position.value,
            "nearest_ma_support": _moving_average_level_report(
                self.moving_averages.nearest_ma_support
            ),
            "nearest_ma_resistance": _moving_average_level_report(
                self.moving_averages.nearest_ma_resistance
            ),
            "short_term_pressure": self.trend_health.short_term_pressure.value,
            "trend_condition": self.trend_health.trend_condition.value,
            "recent_return_pct": self.trend_health.recent_return_pct,
            "consecutive_down_closes": self.trend_health.consecutive_down_closes,
            "consecutive_up_closes": self.trend_health.consecutive_up_closes,
            "pullback_from_recent_high_pct": (self.trend_health.pullback_from_recent_high_pct),
            "bounce_from_recent_low_pct": self.trend_health.bounce_from_recent_low_pct,
            "trend_health_reasons": self.trend_health.trend_health_reasons,
            "multi_timeframe_bias": None,
            "multi_timeframe_alignment": None,
            "multi_timeframe_conflicts": [],
            "audit_reasons": [reason.value for reason in reasons or []],
            "unknown_reasons": _unknown_reasons(self),
        }
        report.update(_market_read_summary(report))
        return report


@dataclass(frozen=True)
class HistoricalAuditEvent:
    """A historical snapshot selected for focused review."""

    snapshot: HistoricalReadSnapshot
    reasons: list[HistoricalAuditReason]

    @property
    def date(self) -> str:
        """Return the event date as an ISO string."""
        return self.snapshot.candle.timestamp.date().isoformat()


@dataclass(frozen=True)
class HistoricalReadReport:
    """Summary of a rolling historical market read."""

    symbol: str
    candles: list[Candle]
    settings: HistoricalReadSettings
    snapshots: list[HistoricalReadSnapshot]
    trend_counts: dict[TrendDirection, int]
    market_type_counts: dict[SidewaysMarketType, int]
    breakout_counts: dict[BreakoutDirection, int]
    bias_counts: dict[HistoricalReadBias, int]
    high_relative_volume_count: int
    confirmed_breakout_count: int

    @property
    def latest_snapshot(self) -> HistoricalReadSnapshot | None:
        """Return the latest historical read snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    @property
    def snapshot_count(self) -> int:
        """Return the number of historical read snapshots."""
        return len(self.snapshots)

    def audit_events(self, *, include_level_events: bool = False) -> list[HistoricalAuditEvent]:
        """Return snapshots where the market read changed or flagged important context."""
        events: list[HistoricalAuditEvent] = []
        previous_snapshot: HistoricalReadSnapshot | None = None

        for snapshot in self.snapshots:
            reasons = _audit_reasons(
                snapshot,
                previous_snapshot,
                include_level_events=include_level_events,
            )
            if reasons:
                events.append(HistoricalAuditEvent(snapshot=snapshot, reasons=reasons))
            previous_snapshot = snapshot

        return events

    def snapshot_debug_reports(
        self,
        *,
        tail: int | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, object]]:
        """Return stable debug reports for rolling snapshots."""
        if tail is not None and tail < 0:
            raise ValueError("tail cannot be negative.")

        snapshots = self.snapshots[-tail:] if tail else self.snapshots
        return [snapshot.to_debug_report(timeframe=timeframe) for snapshot in snapshots]

    def to_debug_report(self, *, timeframe: str | None = None) -> dict[str, object]:
        """Return a stable report-level view of this historical read."""
        min_window = self.settings.min_window or self.settings.lookback
        insufficient_data_reason = (
            f"requires at least {min_window} candles to create a snapshot"
            if not self.snapshots
            else None
        )

        return {
            "symbol": self.symbol,
            "timeframe": timeframe,
            "candle_count": len(self.candles),
            "snapshot_count": self.snapshot_count,
            "lookback": self.settings.lookback,
            "step": self.settings.step,
            "indicator_warmup_lookback": self.settings.indicator_warmup_lookback,
            "min_window": min_window,
            "latest_snapshot": (
                self.latest_snapshot.to_debug_report(timeframe=timeframe)
                if self.latest_snapshot
                else None
            ),
            "trend_counts": _enum_count_report(self.trend_counts),
            "market_type_counts": _enum_count_report(self.market_type_counts),
            "breakout_counts": _enum_count_report(self.breakout_counts),
            "bias_counts": _enum_count_report(self.bias_counts),
            "high_relative_volume_count": self.high_relative_volume_count,
            "confirmed_breakout_count": self.confirmed_breakout_count,
            "insufficient_data_reason": insufficient_data_reason,
        }


def analyze_historical_market(
    candles: Sequence[Candle],
    *,
    settings: HistoricalReadSettings = DEFAULT_HISTORICAL_READ_SETTINGS,
) -> HistoricalReadReport:
    """Run current market readers over rolling historical candle windows."""
    if not candles:
        raise ValueError("candles must contain at least one candle.")

    candle_list = list(candles)
    symbol = candle_list[0].symbol
    min_window = settings.min_window or settings.lookback
    snapshots: list[HistoricalReadSnapshot] = []

    for end_index in range(min_window, len(candle_list) + 1, settings.step):
        window = candle_list[max(0, end_index - settings.lookback) : end_index]
        indicator_window = candle_list[
            max(0, end_index - settings.indicator_warmup_lookback) : end_index
        ]
        snapshot = _analyze_window(
            index=end_index - 1,
            window=window,
            indicator_window=indicator_window,
            settings=settings,
        )
        snapshots.append(snapshot)

    return HistoricalReadReport(
        symbol=symbol,
        candles=candle_list,
        settings=settings,
        snapshots=snapshots,
        trend_counts=_count(snapshot.trend.direction for snapshot in snapshots),
        market_type_counts=_count(snapshot.sideways_market.market_type for snapshot in snapshots),
        breakout_counts=_count(
            snapshot.sideways_market.breakout_direction for snapshot in snapshots
        ),
        bias_counts=_count(snapshot.bias for snapshot in snapshots),
        high_relative_volume_count=sum(
            snapshot.volume.relative_volume_level == RelativeVolumeLevel.HIGH
            for snapshot in snapshots
        ),
        confirmed_breakout_count=sum(
            snapshot.volume.breakout_context == BreakoutVolumeContext.CONFIRMED
            for snapshot in snapshots
        ),
    )


def _analyze_window(
    *,
    index: int,
    window: Sequence[Candle],
    indicator_window: Sequence[Candle],
    settings: HistoricalReadSettings,
) -> HistoricalReadSnapshot:
    trend = analyze_trend(window, strength=settings.trend_strength)
    sideways_market = analyze_sideways_market(window)
    support_resistance = analyze_support_resistance(
        window,
        strength=settings.support_resistance_strength,
    )
    volume = analyze_volume(
        window,
        average_period=settings.volume_average_period,
        breakout_direction=sideways_market.breakout_direction,
    )
    volatility = analyze_volatility(window)
    moving_averages = analyze_moving_average_context(indicator_window)
    trend_health = analyze_trend_health(
        window,
        trend=trend,
        moving_average_context=moving_averages,
    )
    trend_evidence = analyze_trend_evidence(
        window,
        trend=trend,
        sideways_market=sideways_market,
        moving_average_context=moving_averages,
        trend_health=trend_health,
    )

    return HistoricalReadSnapshot(
        index=index,
        candle=window[-1],
        window_size=len(window),
        indicator_window_size=len(indicator_window),
        trend=trend,
        sideways_market=sideways_market,
        support_resistance=support_resistance,
        volume=volume,
        volatility=volatility,
        moving_averages=moving_averages,
        trend_health=trend_health,
        trend_evidence=trend_evidence,
        bias=_classify_bias(trend.direction, sideways_market),
    )


def _classify_bias(
    trend_direction: TrendDirection,
    sideways_market: SidewaysMarketAnalysis,
) -> HistoricalReadBias:
    if sideways_market.breakout_direction == BreakoutDirection.UP:
        return HistoricalReadBias.BULLISH
    if sideways_market.breakout_direction == BreakoutDirection.DOWN:
        return HistoricalReadBias.BEARISH
    if trend_direction == TrendDirection.UPTREND:
        return HistoricalReadBias.BULLISH
    if trend_direction == TrendDirection.DOWNTREND:
        return HistoricalReadBias.BEARISH
    if trend_direction == TrendDirection.SIDEWAYS or sideways_market.is_sideways:
        return HistoricalReadBias.SIDEWAYS
    return HistoricalReadBias.UNKNOWN


def _audit_reasons(
    snapshot: HistoricalReadSnapshot,
    previous_snapshot: HistoricalReadSnapshot | None,
    *,
    include_level_events: bool,
) -> list[HistoricalAuditReason]:
    reasons: list[HistoricalAuditReason] = []

    if previous_snapshot is not None:
        if snapshot.trend.direction != previous_snapshot.trend.direction:
            reasons.append(HistoricalAuditReason.TREND_CHANGED)
        if snapshot.sideways_market.market_type != previous_snapshot.sideways_market.market_type:
            reasons.append(HistoricalAuditReason.MARKET_TYPE_CHANGED)
        if snapshot.bias != previous_snapshot.bias:
            reasons.append(HistoricalAuditReason.BIAS_CHANGED)

    if snapshot.sideways_market.breakout_direction != BreakoutDirection.NONE:
        reasons.append(HistoricalAuditReason.BREAKOUT)
    if snapshot.volume.relative_volume_level == RelativeVolumeLevel.HIGH:
        reasons.append(HistoricalAuditReason.HIGH_RELATIVE_VOLUME)
    if snapshot.volume.breakout_context == BreakoutVolumeContext.CONFIRMED:
        reasons.append(HistoricalAuditReason.CONFIRMED_BREAKOUT_VOLUME)
    if include_level_events:
        if (
            snapshot.support_resistance.nearest_support is not None
            and snapshot.support_resistance.nearest_support.position == LevelPosition.NEAR
        ):
            reasons.append(HistoricalAuditReason.NEAR_SUPPORT)
        if (
            snapshot.support_resistance.nearest_resistance is not None
            and snapshot.support_resistance.nearest_resistance.position == LevelPosition.NEAR
        ):
            reasons.append(HistoricalAuditReason.NEAR_RESISTANCE)

    return reasons


def _count[T](values: Iterable[T]) -> dict[T, int]:
    return dict(Counter(values))


def _swing_point_reports(swing_points: Sequence[SwingPoint]) -> list[dict[str, object]]:
    return [_swing_point_report(point) for point in swing_points]


def _swing_point_report(swing_point: SwingPoint | None) -> dict[str, object] | None:
    if swing_point is None:
        return None

    return {
        "index": swing_point.index,
        "date": swing_point.candle.timestamp.date().isoformat(),
        "type": swing_point.point_type.value,
        "price": swing_point.price,
    }


def _price_level_report(level: PriceLevel | None) -> dict[str, object] | None:
    if level is None:
        return None

    return {
        "type": level.level_type.value,
        "price": level.price,
        "lower_bound": level.lower_bound,
        "upper_bound": level.upper_bound,
        "touches": level.touches,
        "distance_from_close": level.distance_from_close,
        "distance_from_close_pct": level.distance_from_close_pct,
        "position": level.position.value,
        "confidence": level.confidence,
    }


def _moving_average_level_report(
    level: MovingAverageLevel | None,
) -> dict[str, object] | None:
    if level is None:
        return None

    return {
        "name": level.name,
        "period": level.period,
        "value": level.value,
        "position": level.position.value,
        "distance_from_close": level.distance_from_close,
        "distance_from_close_pct": level.distance_from_close_pct,
    }


def _market_read_summary(report: dict[str, object]) -> dict[str, object]:
    status = _market_read_status(report)
    return {
        "market_read_status": status,
        "market_read_summary": _market_read_summary_text(status, report),
        "caution_notes": _caution_notes(report),
        "key_levels_summary": _key_levels_summary(report),
        "actionability": "watch_only",
    }


def _market_read_status(report: dict[str, object]) -> str:
    market_type = report["market_type"]
    trend_direction = report["trend_direction"]
    trend_condition = report["trend_condition"]
    pressure = report["short_term_pressure"]
    trend_candidate = report["trend_candidate"]
    messy_candidate = report["messy_trend_candidate"]

    if market_type == SidewaysMarketType.TRADING_RANGE.value:
        return "trading_range"
    if market_type == SidewaysMarketType.CONSOLIDATION.value:
        return "consolidation"
    if market_type == SidewaysMarketType.CONGESTION.value:
        return "congestion"
    if trend_direction == TrendDirection.UNKNOWN.value:
        return "unknown_insufficient_data"
    if (
        trend_direction == TrendDirection.SIDEWAYS.value
        and messy_candidate
        and trend_candidate == TrendDirection.UPTREND.value
    ):
        return "structural_sideways_with_messy_uptrend_candidate"
    if (
        trend_direction == TrendDirection.SIDEWAYS.value
        and messy_candidate
        and trend_candidate == TrendDirection.DOWNTREND.value
    ):
        return "structural_sideways_with_messy_downtrend_candidate"
    if trend_direction == TrendDirection.UPTREND.value and trend_condition == "pulling_back":
        return "structural_uptrend_with_pullback"
    if trend_direction == TrendDirection.UPTREND.value and trend_condition == "strengthening":
        return "uptrend_strengthening"
    if trend_direction == TrendDirection.DOWNTREND.value and pressure == "bullish":
        return "downtrend_with_bounce"
    if trend_direction == TrendDirection.UPTREND.value:
        return "structural_uptrend"
    if trend_direction == TrendDirection.DOWNTREND.value:
        return "structural_downtrend"
    if trend_direction == TrendDirection.SIDEWAYS.value:
        return "structural_sideways"
    return "unknown_insufficient_data"


def _market_read_summary_text(status: str, report: dict[str, object]) -> str:
    pressure = str(report["short_term_pressure"])
    condition = str(report["trend_condition"])
    ma_context = _summary_ma_context(report)

    if status == "structural_uptrend_with_pullback":
        return f"Structural uptrend with {pressure}_pressure and {condition}; {ma_context}."
    if status == "structural_sideways_with_messy_uptrend_candidate":
        return (
            "Structural sideways market with messy uptrend candidate; "
            f"{pressure}_pressure and {ma_context}."
        )
    if status == "structural_sideways_with_messy_downtrend_candidate":
        return (
            "Structural sideways market with messy downtrend candidate; "
            f"{pressure}_pressure and {ma_context}."
        )
    if status == "trading_range":
        return (
            "Trading range; candidate direction is blocked or neutral; "
            "watch support and resistance boundaries."
        )
    if status == "consolidation":
        return "Consolidation; range-bound context with neutral watch status."
    if status == "congestion":
        return "Congestion; tight range-bound context with neutral watch status."
    if status == "downtrend_with_bounce":
        return f"Structural downtrend with bullish pressure bounce; {ma_context}."
    if status == "uptrend_strengthening":
        return f"Structural uptrend strengthening; {ma_context}."
    if status == "structural_uptrend":
        return f"Structural uptrend; {pressure}_pressure and {ma_context}."
    if status == "structural_downtrend":
        return f"Structural downtrend; {pressure}_pressure and {ma_context}."
    if status == "structural_sideways":
        return f"Structural sideways market; {pressure}_pressure and {ma_context}."
    return "Unknown or insufficient data; watch_only until context is clearer."


def _summary_ma_context(report: dict[str, object]) -> str:
    nearest_support = report["nearest_ma_support"]
    nearest_resistance = report["nearest_ma_resistance"]
    if isinstance(nearest_support, dict):
        return f"price is near {nearest_support['name']} support"
    if isinstance(nearest_resistance, dict):
        return f"price is near {nearest_resistance['name']} resistance"
    return (
        f"EMA20 {report['price_vs_ema_20']}, "
        f"EMA50 {report['price_vs_ema_50']}, "
        f"EMA200 {report['price_vs_ema_200']}"
    )


def _caution_notes(report: dict[str, object]) -> list[str]:
    notes: list[str] = []
    pressure = report["short_term_pressure"]
    condition = report["trend_condition"]
    market_type = report["market_type"]

    if pressure != "unknown":
        notes.append(f"{pressure}_pressure")
    if condition != "unknown":
        notes.append(str(condition))
    if market_type in {
        SidewaysMarketType.TRADING_RANGE.value,
        SidewaysMarketType.CONSOLIDATION.value,
        SidewaysMarketType.CONGESTION.value,
    }:
        notes.append("range_bound")
    if report["trend_candidate_blocked_reason"] is not None:
        notes.append(f"candidate_blocked:{report['trend_candidate_blocked_reason']}")
    if report["trend_candidate_conflict_count"] != 0:
        notes.append("candidate_conflicts")
    notes.extend(_level_position_notes(report))
    return notes


def _level_position_notes(report: dict[str, object]) -> list[str]:
    notes: list[str] = []
    nearest_support = report["nearest_support"]
    nearest_resistance = report["nearest_resistance"]
    if isinstance(nearest_support, dict) and nearest_support.get("position") == "near":
        notes.append("near_support")
    if isinstance(nearest_resistance, dict) and nearest_resistance.get("position") == "near":
        notes.append("near_resistance")
    if "testing_ema50" in report["trend_health_reasons"]:
        notes.append("testing_ema50")
    return notes


def _key_levels_summary(report: dict[str, object]) -> list[str]:
    levels: list[str] = []
    _append_price_level(levels, "nearest_support", report["nearest_support"])
    _append_price_level(levels, "nearest_resistance", report["nearest_resistance"])
    _append_ma_level(levels, "ma_support", report["nearest_ma_support"])
    _append_ma_level(levels, "ma_resistance", report["nearest_ma_resistance"])
    if report["range_lower_bound"] is not None and report["range_upper_bound"] is not None:
        levels.append(f"range {report['range_lower_bound']:.2f}-{report['range_upper_bound']:.2f}")
    return levels


def _append_price_level(
    levels: list[str],
    label: str,
    level: object,
) -> None:
    if isinstance(level, dict):
        levels.append(f"{label} {level['price']:.2f}")


def _append_ma_level(
    levels: list[str],
    label: str,
    level: object,
) -> None:
    if isinstance(level, dict):
        levels.append(f"{label} {level['name']} {level['value']:.2f}")


def _unknown_reasons(snapshot: HistoricalReadSnapshot) -> list[str]:
    reasons: list[str] = []
    if snapshot.trend.direction == TrendDirection.UNKNOWN:
        reasons.append("trend_unknown")
    if snapshot.sideways_market.market_type == SidewaysMarketType.UNKNOWN:
        reasons.append("market_type_unknown")
    if snapshot.volume.relative_volume_level == RelativeVolumeLevel.UNKNOWN:
        reasons.append("relative_volume_unknown")
    if snapshot.volatility.level == VolatilityLevel.UNKNOWN:
        reasons.append("volatility_unknown")
    if snapshot.trend_health.recent_return_pct is None:
        reasons.append("recent_return_unknown")
    if snapshot.moving_averages.ema_200.value is None:
        reasons.append("ema_200_unknown")
    if snapshot.support_resistance.nearest_support is None:
        reasons.append("nearest_support_unknown")
    if snapshot.support_resistance.nearest_resistance is None:
        reasons.append("nearest_resistance_unknown")
    return reasons


def _enum_count_report(counts: dict[object, int]) -> dict[str, int]:
    return {
        key.value if hasattr(key, "value") else str(key): value for key, value in counts.items()
    }
