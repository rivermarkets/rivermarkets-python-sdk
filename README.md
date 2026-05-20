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
