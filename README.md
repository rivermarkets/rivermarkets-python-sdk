# River Markets Python SDK

Python SDK for the [River Markets API](https://docs.rivermarkets.com).

## Installation

```bash
pip install rivermarkets
```

## Usage

```python
from rivermarkets import RiverMarkets

client = RiverMarkets(api_key="your_api_key")

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

client = AsyncRiverMarkets(api_key="your_api_key")
results = await client.markets.search_markets(q="bitcoin")
```
