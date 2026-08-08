import asyncio
import base64
import json
from typing import Any, Dict, List

import httpx
import pytest

from rivermarkets import AsyncRiverMarkets, FeeScheduleNotFoundError, RiverMarkets

PRIVATE_KEY = base64.b64encode(bytes(range(32))).decode()


def _schedule(river_id: int) -> Dict[str, Any]:
    return {
        "river_id": river_id,
        "exchange": "KALSHI",
        "model": "price_shape_v1",
        "maker": {
            "coefficient": "0.0175",
            "rounding": "ceil_cent",
            "pre_ceiling_cent_decimals": 5,
        },
        "taker": {
            "coefficient": "0.07",
            "rounding": "ceil_cent",
            "pre_ceiling_cent_decimals": 5,
        },
        "schedule_version": "sha256:test",
    }


def _response(request: httpx.Request) -> httpx.Response:
    river_ids = json.loads(request.content)["river_ids"]
    return httpx.Response(
        200,
        json={
            "schedules": [_schedule(river_id) for river_id in river_ids],
            "missing_river_ids": [],
        },
    )


def _client(http_client: httpx.Client) -> RiverMarkets:
    return RiverMarkets(
        key_id="test-key",
        private_key=PRIVATE_KEY,
        base_url="https://qa.api.rivermarkets.com",
        httpx_client=http_client,
    )


def test_compute_fee_fetches_once_then_uses_per_client_cache() -> None:
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _client(http_client)
        assert client.compute_fee(123, 4, 0.5) == 0.07
        assert client.compute_fee(123, 4, 0.5) == 0.07
        assert len(requests) == 1

        client.clear_fee_schedule_cache(123)
        assert client.compute_fee(123, 4, 0.5) == 0.07
        assert len(requests) == 2


def test_fee_schedule_cache_is_not_shared_between_clients() -> None:
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as first_http_client:
        with httpx.Client(transport=transport) as second_http_client:
            assert _client(first_http_client).compute_fee(123, 4, 0.5) == 0.07
            assert _client(second_http_client).compute_fee(123, 4, 0.5) == 0.07

    assert len(requests) == 2


def test_prefetch_deduplicates_and_chunks_requests() -> None:
    batches: List[List[int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        batch = json.loads(request.content)["river_ids"]
        batches.append(batch)
        return _response(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _client(http_client)
        client.prefetch_fee_schedules([*range(1, 1003), 1, 2])
        assert [len(batch) for batch in batches] == [1000, 2]

        assert client.compute_fee(1, 4, 0.5) == 0.07
        assert client.compute_fee(1002, 4, 0.5) == 0.07
        assert [len(batch) for batch in batches] == [1000, 2]


def test_missing_schedule_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        river_ids = json.loads(request.content)["river_ids"]
        return httpx.Response(
            200,
            json={"schedules": [], "missing_river_ids": river_ids},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = _client(http_client)
        with pytest.raises(FeeScheduleNotFoundError) as error:
            client.compute_fee(404, 1, 0.5)

    assert error.value.river_ids == (404,)


def test_async_compute_fee_coalesces_concurrent_initial_lookups() -> None:
    async def run() -> None:
        requests: List[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            await asyncio.sleep(0)
            return _response(request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = AsyncRiverMarkets(
                key_id="test-key",
                private_key=PRIVATE_KEY,
                base_url="https://qa.api.rivermarkets.com",
                httpx_client=http_client,
            )
            fees = await asyncio.gather(
                client.compute_fee(123, 4, 0.5),
                client.compute_fee(123, 8, 0.5),
                client.compute_fee(123, 16, 0.5),
            )
            assert fees == [0.07, 0.14, 0.28]
            assert len(requests) == 1

            client.clear_fee_schedule_cache()
            await client.prefetch_fee_schedules([123])
            assert len(requests) == 2

    asyncio.run(run())
