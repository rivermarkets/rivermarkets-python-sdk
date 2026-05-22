"""Ed25519 signing for WebSocket URLs.

The WebSocket handshake reuses the REST auth keypair but encodes the
signature in query params (browsers can't set headers on a WS handshake).
The canonical string the server validates against is:

    WS\\n{path}\\n{sorted_query}\\n{ts}

where {sorted_query} omits key_id/ts/sig and percent-encodes per RFC 3986
with keys sorted alphabetically.
"""

from __future__ import annotations

import base64
import time
import typing
from urllib.parse import quote, urlencode

from nacl.signing import SigningKey


def sign_ws_url(
    *,
    base_url: str,
    path: str,
    key_id: str,
    signing_key: SigningKey,
    extra_query: typing.Optional[typing.Dict[str, str]] = None,
) -> str:
    """Return a fully-signed wss:// URL ready for websockets.connect()."""
    extra = dict(extra_query or {})
    ts = str(int(time.time()))
    sorted_query = urlencode(sorted(extra.items()), quote_via=quote)
    canonical = "\n".join(["WS", path, sorted_query, ts]).encode()
    sig = base64.b64encode(signing_key.sign(canonical).signature).decode()
    params = {**extra, "key_id": key_id, "ts": ts, "sig": sig}
    return f"{base_url}{path}?{urlencode(params, quote_via=quote)}"
