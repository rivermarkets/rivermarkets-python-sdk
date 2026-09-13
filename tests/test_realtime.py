"""Tests for the hand-written realtime client against a local WebSocket server."""

import asyncio
import base64
import json
import time

import pytest
import websockets
from nacl.signing import SigningKey

from rivermarkets.realtime import FatalCloseError, RealtimeClient


PRIVATE_KEY = base64.b64encode(bytes(SigningKey.generate())).decode()


class Server:
    """One-off ``websockets.serve`` wrapper that records what the client sent."""

    def __init__(self, on_connect):
        self._on_connect = on_connect
        self.connections = 0
        self.frames = []

    async def _handler(self, ws):
        self.connections += 1
        conn = self.connections
        await self._on_connect(ws, conn, self)

    async def __aenter__(self):
        self._server = await websockets.serve(self._handler, "127.0.0.1", 0)
        port = self._server.sockets[0].getsockname()[1]
        return RealtimeClient(
            key_id="key",
            private_key=PRIVATE_KEY,
            base_url=f"ws://127.0.0.1:{port}",
            reconnect_delay_s=0.05,
        )

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()


async def echo_until_closed(ws, conn, server):
    await ws.send(json.dumps({"type": "connected", "conn": conn}))
    try:
        async for raw in ws:
            server.frames.append((conn, json.loads(raw)))
            await ws.send(json.dumps({"type": "ack", "conn": conn}))
    except websockets.ConnectionClosed:
        pass


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, timeout=5))


def test_fatal_close_code_raises_instead_of_reconnecting():
    async def reject(ws, conn, server):
        await ws.close(code=4401, reason="invalid auth")

    async def scenario():
        server = Server(reject)
        async with server as client:
            with pytest.raises(FatalCloseError) as info:
                async with client.orders(subaccount_id="sub") as stream:
                    async for _ in stream:
                        pass
            assert info.value.code == 4401
            assert info.value.reason == "invalid auth"
        assert server.connections == 1

    run(scenario())


def test_non_fatal_close_reconnects_and_resubscribes():
    async def drop_first(ws, conn, server):
        await ws.send(json.dumps({"type": "connected", "conn": conn}))
        try:
            async for raw in ws:
                server.frames.append((conn, json.loads(raw)))
                if conn == 1:
                    await ws.close(code=4503, reason="draining")
                    return
                await ws.send(json.dumps({"type": "ack", "conn": conn}))
        except websockets.ConnectionClosed:
            pass

    async def scenario():
        server = Server(drop_first)
        async with server as client:
            types = []
            async with client.orderbooks([2, 1]) as stream:
                async for msg in stream:
                    types.append((msg.type, msg.conn))
                    if msg.type == "connected" and msg.conn == 1:
                        await stream.subscribe([5])
                    if msg.type == "ack":
                        break
        assert server.connections == 2
        assert server.frames[0] == (1, {"action": "subscribe", "river_ids": [1, 2]})
        # The reconnect re-sends the full active set, including the mid-stream add.
        assert server.frames[-1] == (
            2,
            {"action": "subscribe", "river_ids": [1, 2, 5]},
        )

    run(scenario())


def test_close_stops_iteration_promptly_without_reconnect(caplog):
    async def scenario():
        server = Server(echo_until_closed)
        async with server as client:
            stream = client.fills(subaccount_id="sub")
            await stream.__aenter__()
            first = await stream.__anext__()
            assert first.type == "connected"

            async def close_soon():
                await asyncio.sleep(0.05)
                await stream.close()

            closer = asyncio.create_task(close_soon())
            started = time.monotonic()
            with pytest.raises(StopAsyncIteration):
                await stream.__anext__()
            await closer
            elapsed = time.monotonic() - started
            # The old code slept reconnect_delay_s and logged a reconnect
            # warning before noticing the subscription was closed.
            assert elapsed < 1.0
        assert server.connections == 1
        assert "reconnecting" not in caplog.text

    run(scenario())


def test_subscription_is_reusable_after_close():
    async def scenario():
        server = Server(echo_until_closed)
        async with server as client:
            stream = client.tradeprints([7])
            async with stream:
                assert (await stream.__anext__()).type == "connected"
            async with stream:
                assert (await stream.__anext__()).type == "connected"
        assert server.connections == 2

    run(scenario())


def test_subscribe_on_dead_socket_does_not_raise():
    async def close_after_first_frame(ws, conn, server):
        await ws.recv()
        await ws.close(code=1011, reason="overflow")

    async def scenario():
        server = Server(close_after_first_frame)
        async with server as client:
            stream = client.orderbooks([1])
            await stream.__aenter__()
            # Let the server-side close land before the iterator notices it.
            await asyncio.sleep(0.05)
            await stream.subscribe([2])
            await stream.unsubscribe([1])
            assert stream._river_ids == {2}
            await stream.close()

    run(scenario())
