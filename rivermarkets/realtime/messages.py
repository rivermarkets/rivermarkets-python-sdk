"""Inbound WebSocket frame models.

The server's frame schema isn't uniform across endpoints — they share a few
types (`error`, `connected`, `reconnect`) and each adds its own (`snapshot`
and `update` for orderbooks, `order` for orders, `trade` for tradeprints).
We model this as one open envelope and let callers switch on `msg.type`.
"""

from __future__ import annotations

import typing

from pydantic import BaseModel, ConfigDict


class Message(BaseModel):
    """A generic inbound WebSocket frame.

    Always has `type`. Endpoint-specific fields (`data`, `river_id`, `orders`,
    `code`, `message`, ...) are kept as extras — access them via attribute
    access or `msg.model_extra`.
    """

    type: str

    model_config = ConfigDict(extra="allow")


def parse_message(payload: typing.Mapping[str, typing.Any]) -> Message:
    return Message.model_validate(payload)
