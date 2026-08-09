# River Markets Python SDK

Python SDK for the [River Markets API](https://docs.rivermarkets.com).

## Installation

```bash
pip install rivermarkets
```

## Authentication

The SDK authenticates with Ed25519 request signing. Create an API key in
Settings → API Keys; you'll get a **Key ID** (UUID) and a **base64-encoded
private key** (shown once at creation). Pass both to the client — every
request is signed transparently via `X-River-Key-Id`, `X-River-Timestamp`,
and `X-River-Signature` headers.

## Usage

```python
from rivermarkets import RiverMarkets

client = RiverMarkets(
    key_id="YOUR_KEY_ID",
    private_key="YOUR_BASE64_PRIVATE_KEY",
)

# Search markets
results = client.markets.search_markets(q="bitcoin")

# Place an order
order = client.orders.create_order(
    subaccount_id="...",
    river_id=4552150,
    order_type="LIMIT",
    time_in_force="GTC",
    buy_flag=True,
    price=0.50,
    qty=10,
)

# Cancel an order
client.orders.cancel_order(order_id="...")
```

### Async

```python
from rivermarkets import AsyncRiverMarkets

client = AsyncRiverMarkets(
    key_id="YOUR_KEY_ID",
    private_key="YOUR_BASE64_PRIVATE_KEY",
)
results = await client.markets.search_markets(q="bitcoin")
```

## Local fee calculations

The client fetches each market's live fee schedule once and caches it for the
lifetime of that client. You can also warm several schedules with one request:

```python
from rivermarkets import RiverMarkets

client = RiverMarkets(
    key_id="YOUR_KEY_ID",
    private_key="YOUR_BASE64_PRIVATE_KEY",
)

river_id = 4552150
qty = 10
price = 0.50

client.prefetch_fee_schedules([river_id])

taker_fee = client.compute_fee(
    river_id=river_id,
    qty=qty,
    price=price,
    is_maker=False,
)
maker_fee = client.compute_fee(
    river_id=river_id,
    qty=qty,
    price=price,
    is_maker=True,
)

# Normalize quoted prices to include the per-contract taker fee.
buy_all_in = price + taker_fee / qty
sell_net = price - taker_fee / qty
```

`compute_fee` makes no network request after the River ID is cached. Call
`clear_fee_schedule_cache(river_id)` to force the next calculation to reload
that schedule.
