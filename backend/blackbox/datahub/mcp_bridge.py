"""Routes the investigator's DataHub read tools through the official DataHub MCP
Server (`uvx mcp-server-datahub`), making BlackBox itself a real MCP client of
DataHub's agent surface. Falls back to the direct GraphQL client on any failure,
so MCP enriches the integration without becoming a single point of failure.

The bridge owns a dedicated asyncio loop in a daemon thread; sync callers use
`call_tool(name, args)`.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any

from ..config import settings

_START_TIMEOUT = 60
_CALL_TIMEOUT = 45


class McpBridge:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session = None
        self._exit_stack = None
        self._tools: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._failed: str | None = None

    # ---------------------------------------------------------------- lifecycle

    def ensure_started(self) -> bool:
        with self._lock:
            if self._session is not None:
                return True
            if self._failed is not None:
                return False
            try:
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever, daemon=True, name="datahub-mcp-bridge"
                )
                self._thread.start()
                fut = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
                fut.result(timeout=_START_TIMEOUT)
                return True
            except Exception as e:
                self._failed = f"{type(e).__name__}: {e}"
                return False

    async def _connect(self) -> None:
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = settings.datahub_gms_url
        if settings.datahub_gms_token:
            env["DATAHUB_GMS_TOKEN"] = settings.datahub_gms_token
        params = StdioServerParameters(
            command="uvx", args=["mcp-server-datahub@latest"], env=env
        )
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        listed = await self._session.list_tools()
        self._tools = {t.name: t for t in listed.tools}

    # ------------------------------------------------------------------- calls

    @property
    def available(self) -> bool:
        return self.ensure_started()

    @property
    def failure(self) -> str | None:
        return self._failed

    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        if not self.ensure_started():
            raise RuntimeError(f"MCP bridge unavailable: {self._failed}")
        fut = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, args), self._loop
        )
        result = fut.result(timeout=_CALL_TIMEOUT)
        if getattr(result, "isError", False):
            raise RuntimeError(f"MCP tool {name} errored: {_content_to_text(result)[:500]}")
        text = _content_to_text(result)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text


def _content_to_text(result: Any) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        if getattr(block, "type", "") == "text":
            parts.append(block.text)
    return "\n".join(parts)


bridge = McpBridge()
