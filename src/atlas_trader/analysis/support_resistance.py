"""Support, resistance, and moving-average context helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from atlas_trader.analysis.trends import SwingPoint, SwingPointType, find_swing_points
from atlas_trader.data.models import Candle


class LevelType(StrEnum):
    """Type of price level."""

    SUPPORT = "support"
    RESISTANCE = "resistance"


class LevelPosition(StrEnum):
    """Where the latest close sits relative to a level."""

    BELOW = "below"
    NEAR = "near"
    ABOVE = "above"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SupportResistanceSettings:
    """Tunable thresholds used by support/resistance detection."""

    default_swing_strength: int = 2
    level_tolerance_ratio: float = 0.01
    proximity_ratio: float = 0.02
    min_touches: int = 2
    max_levels: int = 8
    default_moving_average_period: int = 20

    def __post_init__(self) -> None:
        """Validate support/resistance settings."""
        if self.default_swing_strength <= 0:
            raise ValueError("default_swing_strength must be greater than zero.")
        if self.level_tolerance_ratio < 0:
            raise ValueError("level_tolerance_ratio cannot be negative.")
        if self.proximity_ratio < 0:
            raise ValueError("proximity_ratio cannot be negative.")
        if self.min_touches <= 0:
            raise ValueError("min_touches must be greater than zero.")
        if self.max_levels <= 0:
            raise ValueError("max_levels must be greater than zero.")
        if self.default_moving_average_period <= 0:
            raise ValueError("default_moving_average_period must be greater than zero.")


# TODO(v0.7): Move support/resistance thresholds into a shared analysis config object.
DEFAULT_SUPPORT_RESISTANCE_SETTINGS = SupportResistanceSettings()


@dataclass(frozen=True)
class PriceLevel:
    """A detected support or resistance price zone."""

    level_type: LevelType
    price: float
    lower_bound: float
    upper_bound: float
    touches: int
    swing_points: list[SwingPoint]
    distance_from_close: float | None
    distance_from_close_pct: float | None
    position: LevelPosition
    confidence: float


@dataclass(frozen=True)
class MovingAverageContext:
    """Latest close relative to a simple moving average."""

    period: int
    value: float | None
    distance_from_close: float | None
    distance_from_close_pct: float | None
    position: LevelPosition


@dataclass(frozen=True)
class SupportResistanceAnalysis:
    """Detected support/resistance levels for a candle window."""

    support_levels: list[PriceLevel]
    resistance_levels: list[PriceLevel]
    nearest_support: PriceLevel | None
    nearest_resistance: PriceLevel | None
    moving_average: MovingAverageContext | None


def analyze_support_resistance(
    candles: Sequence[Candle],
    *,
    lookback: int | None = None,
    strength: int | None = None,
    include_moving_average: bool = True,
    moving_average_period: int | None = None,
    settings: SupportResistanceSettings = DEFAULT_SUPPORT_RESISTANCE_SETTINGS,
) -> SupportResistanceAnalysis:
    """Detect support and resistance levels from clustered swing highs and lows."""
    _validate_lookback(lookback)
    strength = settings.default_swing_strength if strength is None else strength
    _validate_strength(strength)
    resolved_moving_average_period = (
        _resolve_moving_average_period(moving_average_period, settings)
        if include_moving_average
        else None
    )

    window = list(candles[-lookback:] if lookback is not None else candles)
    if not window:
        return SupportResistanceAnalysis(
            support_levels=[],
            resistance_levels=[],
            nearest_support=None,
            nearest_resistance=None,
            moving_average=(
                moving_average_context(
                    window,
                    period=resolved_moving_average_period,
                    settings=settings,
                )
                if include_moving_average
                else None
            ),
        )

    latest_close = window[-1].close
    swing_points = find_swing_points(window, strength=strength)
    support_levels = _build_levels(
        swing_points=swing_points,
        candles=window,
        level_type=LevelType.SUPPORT,
        latest_close=latest_close,
        settings=settings,
    )
    resistance_levels = _build_levels(
        swing_points=swing_points,
        candles=window,
        level_type=LevelType.RESISTANCE,
        latest_close=latest_close,
        settings=settings,
    )

    return SupportResistanceAnalysis(
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        nearest_support=_nearest_support(support_levels, latest_close),
        nearest_resistance=_nearest_resistance(resistance_levels, latest_close),
        moving_average=(
            moving_average_context(
                window,
                period=resolved_moving_average_period,
                settings=settings,
            )
            if include_moving_average
            else None
        ),
    )


def simple_moving_average(values: Sequence[float], period: int) -> float | None:
    """Return the simple moving average for the latest `period` values."""
    _validate_period(period)
    if len(values) < period:
        return None

    return fmean(values[-period:])


def candle_close_moving_average(candles: Sequence[Candle], period: int) -> float | None:
    """Return the simple moving average of candle closes."""
    return simple_moving_average([candle.close for candle in candles], period)


def moving_average_context(
    candles: Sequence[Candle],
    *,
    period: int | None = None,
    settings: SupportResistanceSettings = DEFAULT_SUPPORT_RESISTANCE_SETTINGS,
) -> MovingAverageContext:
    """Return latest close context relative to a close-price simple moving average."""
    period = settings.default_moving_average_period if period is None else period
    _validate_period(period)
    if not candles:
        return MovingAverageContext(
            period=period,
            value=None,
            distance_from_close=None,
            distance_from_close_pct=None,
            position=LevelPosition.UNKNOWN,
        )

    value = candle_close_moving_average(candles, period)
    latest_close = candles[-1].close
    if value is None or latest_close <= 0:
        return MovingAverageContext(
            period=period,
            value=value,
            distance_from_close=None,
            distance_from_close_pct=None,
            position=LevelPosition.UNKNOWN,
        )

    distance = latest_close - value
    distance_pct = distance / latest_close
    return MovingAverageContext(
        period=period,
        value=value,
        distance_from_close=distance,
        distance_from_close_pct=distance_pct,
        position=_position_for(latest_close, value, settings.proximity_ratio),
    )


def _validate_lookback(lookback: int | None) -> None:
    if lookback is not None and lookback <= 1:
        raise ValueError("lookback must be greater than one.")


def _validate_strength(strength: int) -> None:
    if strength <= 0:
        raise ValueError("strength must be greater than zero.")


def _validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("period must be greater than zero.")


def _resolve_moving_average_period(
    period: int | None,
    settings: SupportResistanceSettings,
) -> int:
    resolved_period = settings.default_moving_average_period if period is None else period
    _validate_period(resolved_period)
    return resolved_period


def _build_levels(
    *,
    swing_points: Sequence[SwingPoint],
    candles: Sequence[Candle],
    level_type: LevelType,
    latest_close: float,
    settings: SupportResistanceSettings,
) -> list[PriceLevel]:
    point_type = SwingPointType.LOW if level_type == LevelType.SUPPORT else SwingPointType.HIGH
    candidate_points = [point for point in swing_points if point.point_type == point_type]
    clusters = _cluster_swing_points(candidate_points, settings.level_tolerance_ratio)

    levels = [
        _level_from_cluster(
            cluster=cluster,
            candles=candles,
            level_type=level_type,
            latest_close=latest_close,
            settings=settings,
        )
        for cluster in clusters
    ]
    qualifying_levels = [level for level in levels if level.touches >= settings.min_touches]
    return sorted(
        qualifying_levels,
        key=lambda level: (level.confidence, level.touches, -abs(level.price - latest_close)),
        reverse=True,
    )[: settings.max_levels]


def _cluster_swing_points(
    swing_points: Sequence[SwingPoint],
    tolerance_ratio: float,
) -> list[list[SwingPoint]]:
    clusters: list[list[SwingPoint]] = []
    for point in sorted(swing_points, key=lambda swing_point: swing_point.price):
        for cluster in clusters:
            cluster_price = fmean(cluster_point.price for cluster_point in cluster)
            tolerance = cluster_price * tolerance_ratio
            if abs(point.price - cluster_price) <= tolerance:
                cluster.append(point)
                break
        else:
            clusters.append([point])

    return clusters


def _level_from_cluster(
    *,
    cluster: Sequence[SwingPoint],
    candles: Sequence[Candle],
    level_type: LevelType,
    latest_close: float,
    settings: SupportResistanceSettings,
) -> PriceLevel:
    price = fmean(point.price for point in cluster)
    tolerance = price * settings.level_tolerance_ratio
    lower_bound = price - tolerance
    upper_bound = price + tolerance
    touches = _count_touches(candles, level_type, lower_bound, upper_bound)
    distance = latest_close - price if latest_close > 0 else None
    distance_pct = distance / latest_close if distance is not None and latest_close > 0 else None

    return PriceLevel(
        level_type=level_type,
        price=price,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        touches=touches,
        swing_points=list(cluster),
        distance_from_close=distance,
        distance_from_close_pct=distance_pct,
        position=_position_for(latest_close, price, settings.proximity_ratio),
        confidence=_confidence_for(touches, len(cluster), len(candles), settings),
    )


def _count_touches(
    candles: Sequence[Candle],
    level_type: LevelType,
    lower_bound: float,
    upper_bound: float,
) -> int:
    if level_type == LevelType.SUPPORT:
        return sum(lower_bound <= candle.low <= upper_bound for candle in candles)

    return sum(lower_bound <= candle.high <= upper_bound for candle in candles)


def _confidence_for(
    touches: int,
    swing_count: int,
    candle_count: int,
    settings: SupportResistanceSettings,
) -> float:
    if candle_count == 0:
        return 0

    touch_score = min(touches / settings.min_touches, 1.0)
    swing_score = min(swing_count / settings.min_touches, 1.0)
    density_score = min(touches / candle_count * 4, 1.0)
    return round((touch_score + swing_score + density_score) / 3, 4)


def _position_for(close: float, level_price: float, proximity_ratio: float) -> LevelPosition:
    if close <= 0 or level_price <= 0:
        return LevelPosition.UNKNOWN

    tolerance = level_price * proximity_ratio
    if abs(close - level_price) <= tolerance:
        return LevelPosition.NEAR
    if close > level_price:
        return LevelPosition.ABOVE
    return LevelPosition.BELOW


def _nearest_support(levels: Sequence[PriceLevel], latest_close: float) -> PriceLevel | None:
    supports_below_close = [level for level in levels if level.price <= latest_close]
    if not supports_below_close:
        return None

    return max(supports_below_close, key=lambda level: level.price)


def _nearest_resistance(levels: Sequence[PriceLevel], latest_close: float) -> PriceLevel | None:
    resistances_above_close = [level for level in levels if level.price >= latest_close]
    if not resistances_above_close:
        return None

    return min(resistances_above_close, key=lambda level: level.price)
