"""Filter the upstream OpenAPI spec to the set of routes we publicly document.

Run this between `curl ... > openapi.raw.json` and `fern generate --local`.
Reads `openapi.raw.json`, writes `openapi.json`, prunes orphan component
schemas so the generated SDK doesn't ship types for endpoints it can't call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "openapi.raw.json"
OUT = HERE / "openapi.json"

# (path, method) tuples that mirror docs.rivermarkets.com/api-reference.
# Sourced from llms.txt — keep this list in sync when the docs change.
ALLOWED: set[tuple[str, str]] = {
    # complex-orders
    ("/v1/complex-orders", "get"),
    ("/v1/complex-orders", "post"),
    ("/v1/complex-orders/cancel-all", "post"),
    ("/v1/complex-orders/{complex_order_id}", "get"),
    ("/v1/complex-orders/{complex_order_id}", "delete"),
    # fills
    ("/v1/fills", "get"),
    # generic-assets
    ("/v1/generic-assets", "get"),
    ("/v1/generic-assets", "post"),
    ("/v1/generic-assets/{generic_asset_id}", "get"),
    ("/v1/generic-assets/{generic_asset_id}", "patch"),
    ("/v1/generic-assets/{generic_asset_id}", "delete"),
    ("/v1/generic-assets/{generic_asset_id}/members", "post"),
    ("/v1/generic-assets/{generic_asset_id}/members", "delete"),
    # markets
    ("/v1/markets/lookup", "get"),
    ("/v1/markets/match", "get"),
    ("/v1/markets/match/batch", "post"),
    ("/v1/markets/search", "get"),
    # orderbooks
    ("/v1/orderbooks/{river_id}", "get"),
    # orders
    ("/v1/orders", "post"),
    ("/v1/orders", "get"),
    ("/v1/orders/cancel-all", "post"),
    ("/v1/orders/{order_id}", "get"),
    ("/v1/orders/{order_id}", "delete"),
    ("/v1/orders/{order_id}", "patch"),
    # positions
    ("/v1/positions", "get"),
    # prices
    ("/v1/prices/{river_id}", "get"),
    # tradeprints
    ("/v1/tradeprints", "get"),
    # subaccounts
    ("/v1/subaccounts", "get"),
    ("/v1/subaccounts", "post"),
    ("/v1/subaccounts/{subaccount_id}", "get"),
    ("/v1/subaccounts/{subaccount_id}", "patch"),
    ("/v1/subaccounts/{subaccount_id}", "delete"),
}

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}


def filter_paths(spec: dict) -> tuple[dict, list[str]]:
    """Strip out (path, method) pairs that aren't in ALLOWED. Returns (spec, dropped)."""
    dropped: list[str] = []
    new_paths: dict = {}
    for path, methods in spec["paths"].items():
        kept_methods = {}
        for key, value in methods.items():
            if key.lower() not in HTTP_METHODS:
                kept_methods[key] = value
                continue
            if (path, key.lower()) in ALLOWED:
                kept_methods[key] = value
            else:
                dropped.append(f"{key.upper()} {path}")
        # Only keep the path entry if at least one operation survived.
        if any(k.lower() in HTTP_METHODS for k in kept_methods):
            new_paths[path] = kept_methods
    spec["paths"] = new_paths
    return spec, dropped


REF_RE = re.compile(r'"\$ref"\s*:\s*"#/components/schemas/([^"]+)"')


def collect_refs(obj: object) -> set[str]:
    """Walk a JSON-ish structure and return every $ref'd schema name."""
    return set(REF_RE.findall(json.dumps(obj)))


def prune_schemas(spec: dict) -> list[str]:
    """Remove component schemas that aren't (transitively) referenced from paths."""
    schemas = spec.get("components", {}).get("schemas", {})
    if not schemas:
        return []

    reachable = collect_refs(spec.get("paths", {}))
    # Transitive closure: keep walking until no new refs appear.
    frontier = set(reachable)
    while frontier:
        next_frontier: set[str] = set()
        for name in frontier:
            if name in schemas:
                for child in collect_refs(schemas[name]):
                    if child not in reachable:
                        next_frontier.add(child)
        reachable |= next_frontier
        frontier = next_frontier

    dropped = [name for name in schemas if name not in reachable]
    spec["components"]["schemas"] = {
        name: schema for name, schema in schemas.items() if name in reachable
    }
    return dropped


def main() -> None:
    spec = json.loads(RAW.read_text())
    spec, dropped_routes = filter_paths(spec)
    dropped_schemas = prune_schemas(spec)
    OUT.write_text(json.dumps(spec, indent=2) + "\n")

    print(f"Wrote {OUT.relative_to(HERE.parent)}")
    print(f"  routes kept    : {sum(1 for p,m in spec['paths'].items() for k in m if k.lower() in HTTP_METHODS)}")
    print(f"  routes dropped : {len(dropped_routes)}")
    for r in dropped_routes:
        print(f"    - {r}")
    print(f"  schemas dropped: {len(dropped_schemas)}")


if __name__ == "__main__":
    main()
