from dataclasses import dataclass
from typing import Optional

import pytest

from rivermarkets import (
    FeeRuleResponse,
    FeeScheduleResponse,
    UnsupportedFeeScheduleError,
    compute_fee_from_schedule,
)


@dataclass(frozen=True)
class FeeCase:
    exchange: str
    qty: float
    price: float
    is_maker: bool
    taker_rate: Optional[float]
    expected: float


def _schedule(exchange: str, taker_rate: Optional[float]) -> FeeScheduleResponse:
    if exchange == "KALSHI":
        maker = FeeRuleResponse(
            coefficient="0.0175",
            rounding="ceil_cent",
            pre_ceiling_cent_decimals=5,
        )
        taker = FeeRuleResponse(
            coefficient="0.07",
            rounding="ceil_cent",
            pre_ceiling_cent_decimals=5,
        )
    elif exchange == "POLYMARKET":
        maker = FeeRuleResponse(
            coefficient="0",
            rounding="none",
            pre_ceiling_cent_decimals=None,
        )
        taker = FeeRuleResponse(
            coefficient=str(taker_rate or 0.0),
            rounding="none",
            pre_ceiling_cent_decimals=None,
        )
    else:
        maker = FeeRuleResponse(
            coefficient="0",
            rounding="none",
            pre_ceiling_cent_decimals=None,
        )
        taker = FeeRuleResponse(
            coefficient=str(taker_rate or 0.0),
            rounding="half_even_cent",
            pre_ceiling_cent_decimals=None,
        )
    return FeeScheduleResponse(
        river_id=1,
        exchange=exchange,
        model="price_shape_v1",
        maker=maker,
        taker=taker,
        schedule_version="sha256:test",
    )


CASES = [
    pytest.param(
        FeeCase("KALSHI", 4, 0.5, False, None, 0.07), id="kalshi-taker-float-artifact"
    ),
    pytest.param(
        FeeCase("KALSHI", 1, 0.5, False, None, 0.02), id="kalshi-taker-half-cent"
    ),
    pytest.param(
        FeeCase("KALSHI", 8, 0.5, True, None, 0.04), id="kalshi-maker-half-cent"
    ),
    pytest.param(
        FeeCase("KALSHI", 16, 0.5, True, None, 0.07), id="kalshi-maker-float-artifact"
    ),
    pytest.param(FeeCase("KALSHI", 1, 0.01, False, None, 0.01), id="kalshi-tail-one"),
    pytest.param(
        FeeCase("KALSHI", 100, 0.01, False, None, 0.07), id="kalshi-tail-many"
    ),
    pytest.param(
        FeeCase("KALSHI", 37, 0.37, False, None, 0.61), id="kalshi-asymmetric"
    ),
    pytest.param(
        FeeCase("KALSHI", 4, 0.5, False, None, 0.07), id="kalshi-default-price"
    ),
    pytest.param(
        FeeCase("KALSHI", 4, 0.5, False, None, 0.07), id="kalshi-worst-case-price"
    ),
    pytest.param(
        FeeCase("KALSHI", 2.75, 0.33333, False, None, 0.05), id="kalshi-fractional"
    ),
    pytest.param(
        FeeCase("POLYMARKET", 100, 0.5, True, 0.08, 0.0), id="polymarket-maker"
    ),
    pytest.param(
        FeeCase("POLYMARKET", 100, 0.5, False, 0.08, 2.0), id="polymarket-taker"
    ),
    pytest.param(
        FeeCase("POLYMARKET", 3.7, 0.13, False, 0.0123, 0.005147181),
        id="polymarket-fractional",
    ),
    pytest.param(
        FeeCase("POLYMARKET", 10, 0.5, False, None, 0.0), id="polymarket-no-config"
    ),
    pytest.param(
        FeeCase("POLYMARKET", 10, 0.5, False, 0.06, 0.15), id="polymarket-default-price"
    ),
    pytest.param(
        FeeCase("POLYMARKET", 10, 0.5, False, 0.06, 0.15),
        id="polymarket-worst-case-price",
    ),
    pytest.param(
        FeeCase("POLYMARKET", 10, 0.5, False, 0.0, 0.0), id="polymarket-zero-rate"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 100, 0.5, True, 0.08, 0.0), id="polymarket-us-maker"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 10, 0.5, False, None, 0.0),
        id="polymarket-us-no-config",
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 1, 0.5, False, 0.02, 0.0), id="half-even-0.005"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 3, 0.5, False, 0.02, 0.02), id="half-even-0.015"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 5, 0.5, False, 0.02, 0.02), id="half-even-0.025"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 7, 0.5, False, 0.02, 0.04), id="half-even-0.035"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 1, 0.1, False, 0.1, 0.01), id="polymarket-us-non-tie"
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 1, 0.5, False, 0.02, 0.0),
        id="polymarket-us-default-price",
    ),
    pytest.param(
        FeeCase("POLYMARKET_US", 3, 0.5, False, 0.02, 0.02),
        id="polymarket-us-worst-case-price",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_fee_calculation_matches_riverlib_regression_matrix(case: FeeCase) -> None:
    assert (
        compute_fee_from_schedule(
            _schedule(case.exchange, case.taker_rate),
            qty=case.qty,
            price=case.price,
            is_maker=case.is_maker,
        )
        == case.expected
    )


def test_kalshi_stabilizes_float_noise_before_ceiling() -> None:
    schedule = _schedule("KALSHI", None)
    raw_fee = 4 * float(schedule.taker.coefficient) * 0.5 * (1 - 0.5)

    assert raw_fee * 100 == 7.000000000000001
    assert compute_fee_from_schedule(schedule, 4, 0.5, False) == 0.07


def test_unknown_model_is_rejected() -> None:
    schedule = _schedule("KALSHI", None).model_copy(update={"model": "future_model"})

    with pytest.raises(UnsupportedFeeScheduleError, match="future_model"):
        compute_fee_from_schedule(schedule, 1, 0.5, False)


def test_ceil_cent_requires_stabilization_precision() -> None:
    schedule = _schedule("KALSHI", None)
    broken_taker = schedule.taker.model_copy(update={"pre_ceiling_cent_decimals": None})
    schedule = schedule.model_copy(update={"taker": broken_taker})

    with pytest.raises(
        UnsupportedFeeScheduleError,
        match="pre_ceiling_cent_decimals",
    ):
        compute_fee_from_schedule(schedule, 1, 0.5, False)


def test_unknown_rounding_is_rejected() -> None:
    schedule = _schedule("KALSHI", None)
    unknown_rule = schedule.taker.model_copy(update={"rounding": "future_rounding"})
    schedule = schedule.model_copy(update={"taker": unknown_rule})

    with pytest.raises(UnsupportedFeeScheduleError, match="future_rounding"):
        compute_fee_from_schedule(schedule, 1, 0.5, False)
