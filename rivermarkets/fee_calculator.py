"""Cached fee calculation using live schedules from the River Markets API."""

from __future__ import annotations

import asyncio
import math
import typing
from decimal import ROUND_HALF_EVEN, Decimal

from .types.fee_schedule_lookup_response import FeeScheduleLookupResponse
from .types.fee_schedule_response import FeeScheduleResponse

if typing.TYPE_CHECKING:
    from .fees.client import AsyncFeesClient, FeesClient


_CENT = Decimal("0.01")
_MAX_LOOKUP_SIZE = 1000


class UnsupportedFeeScheduleError(ValueError):
    """The SDK does not implement a schedule model or rounding rule."""


class FeeScheduleNotFoundError(LookupError):
    """The API did not return schedules for one or more River IDs."""

    def __init__(self, river_ids: typing.Sequence[int]):
        self.river_ids = tuple(river_ids)
        joined = ", ".join(str(river_id) for river_id in self.river_ids)
        super().__init__(f"Fee schedule not found for River ID(s): {joined}")


def compute_fee_from_schedule(
    schedule: FeeScheduleResponse,
    qty: float,
    price: float,
    is_maker: bool,
) -> float:
    """Reproduce riverlib's versioned fee calculation exactly."""
    if schedule.model != "price_shape_v1":
        raise UnsupportedFeeScheduleError(f"Unsupported fee model: {schedule.model}")

    rule = schedule.maker if is_maker else schedule.taker

    # Operation order and float conversion intentionally match riverlib.
    raw_fee = qty * float(rule.coefficient) * price * (1 - price)

    if rule.rounding == "none":
        return raw_fee
    if rule.rounding == "ceil_cent":
        precision = rule.pre_ceiling_cent_decimals
        if precision is None:
            raise UnsupportedFeeScheduleError(
                "ceil_cent requires pre_ceiling_cent_decimals"
            )
        stabilized_cents = round(raw_fee * 100, precision)
        return math.ceil(stabilized_cents) / 100
    if rule.rounding == "half_even_cent":
        return float(Decimal(repr(raw_fee)).quantize(_CENT, rounding=ROUND_HALF_EVEN))
    raise UnsupportedFeeScheduleError(f"Unsupported fee rounding: {rule.rounding}")


def _uncached_ids(
    river_ids: typing.Sequence[int], cache: typing.Mapping[int, FeeScheduleResponse]
) -> typing.List[int]:
    return list(
        dict.fromkeys(river_id for river_id in river_ids if river_id not in cache)
    )


def _chunks(river_ids: typing.Sequence[int]) -> typing.Iterator[typing.Sequence[int]]:
    for start in range(0, len(river_ids), _MAX_LOOKUP_SIZE):
        yield river_ids[start : start + _MAX_LOOKUP_SIZE]


def _store_response(
    response: FeeScheduleLookupResponse,
    requested_ids: typing.Sequence[int],
    cache: typing.MutableMapping[int, FeeScheduleResponse],
) -> typing.List[int]:
    cache.update({schedule.river_id: schedule for schedule in response.schedules})
    reported_missing = set(response.missing_river_ids)
    return [
        river_id
        for river_id in requested_ids
        if river_id in reported_missing or river_id not in cache
    ]


class SyncFeeCalculator:
    """Per-client synchronous fee schedule cache and calculator."""

    def __init__(self, fees_client: "FeesClient"):
        self._fees_client = fees_client
        self._schedule_cache: typing.Dict[int, FeeScheduleResponse] = {}

    def compute_fee(
        self, river_id: int, qty: float, price: float, is_maker: bool = False
    ) -> float:
        self.prefetch_fee_schedules([river_id])
        return compute_fee_from_schedule(
            self._schedule_cache[river_id], qty, price, is_maker
        )

    def prefetch_fee_schedules(self, river_ids: typing.Sequence[int]) -> None:
        missing_ids: typing.List[int] = []
        for chunk in _chunks(_uncached_ids(river_ids, self._schedule_cache)):
            response = self._fees_client.lookup_fee_schedules(river_ids=chunk)
            missing_ids.extend(_store_response(response, chunk, self._schedule_cache))
        if missing_ids:
            raise FeeScheduleNotFoundError(missing_ids)

    def clear_fee_schedule_cache(self, river_id: typing.Optional[int] = None) -> None:
        if river_id is None:
            self._schedule_cache.clear()
        else:
            self._schedule_cache.pop(river_id, None)


class AsyncFeeCalculator:
    """Per-client asynchronous fee schedule cache and calculator."""

    def __init__(self, fees_client: "AsyncFeesClient"):
        self._fees_client = fees_client
        self._schedule_cache: typing.Dict[int, FeeScheduleResponse] = {}
        self._lookup_lock = asyncio.Lock()

    async def compute_fee(
        self, river_id: int, qty: float, price: float, is_maker: bool = False
    ) -> float:
        await self.prefetch_fee_schedules([river_id])
        return compute_fee_from_schedule(
            self._schedule_cache[river_id], qty, price, is_maker
        )

    async def prefetch_fee_schedules(self, river_ids: typing.Sequence[int]) -> None:
        async with self._lookup_lock:
            missing_ids: typing.List[int] = []
            for chunk in _chunks(_uncached_ids(river_ids, self._schedule_cache)):
                response = await self._fees_client.lookup_fee_schedules(river_ids=chunk)
                missing_ids.extend(
                    _store_response(response, chunk, self._schedule_cache)
                )
            if missing_ids:
                raise FeeScheduleNotFoundError(missing_ids)

    def clear_fee_schedule_cache(self, river_id: typing.Optional[int] = None) -> None:
        if river_id is None:
            self._schedule_cache.clear()
        else:
            self._schedule_cache.pop(river_id, None)
