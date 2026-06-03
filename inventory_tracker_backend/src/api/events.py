from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Set

from starlette.responses import StreamingResponse


class SseBroker:
    """
    Simple in-memory SSE broker.

    - Each connected client gets its own asyncio.Queue.
    - Broadcast pushes a JSON event to all queues.
    - This is process-local (sufficient for preview/single instance).
      For multi-instance deployments, swap with Redis/pubsub, etc.
    """

    def __init__(self) -> None:
        self._queues: Set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def connect(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues.add(q)
        return q

    async def disconnect(self, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._queues.discard(q)

    async def broadcast(self, event: dict) -> None:
        payload = json.dumps(event, separators=(",", ":"))
        async with self._lock:
            queues = list(self._queues)

        # Best-effort: drop if client is slow.
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def event_stream(self) -> AsyncGenerator[bytes, None]:
        """
        Async generator yielding bytes formatted as SSE `data:` messages.
        """
        q = await self.connect()
        try:
            # Kickstart: helps clients know the stream is alive.
            yield b"event: ready\ndata: {\"type\":\"ready\"}\n\n"

            while True:
                data = await q.get()
                # SSE format: each message ends with a blank line.
                yield f"data: {data}\n\n".encode("utf-8")
        except asyncio.CancelledError:
            raise
        finally:
            await self.disconnect(q)


def sse_response(broker: SseBroker) -> StreamingResponse:
    """
    Create a StreamingResponse suitable for SSE consumption.
    """
    return StreamingResponse(
        broker.event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Some proxies buffer by default; this header can help.
            "X-Accel-Buffering": "no",
        },
    )
