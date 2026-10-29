"""A tiny async event bus.

Everything that happens (deaths, PBs, boss changes, manual corrections) is
published here as an Event. The overlay server is one subscriber; plugins
listed in config.toml are others. A Twitch chat bot bridge is meant to be a
plugin that subscribes to this bus; see examples/webhook_forwarder.py.

Event types: death, death_undone, new_pb, defeated, defeated_cancel, kill,
boss_engaged, boss_changed, boss_reset, phase, game_changed. defeated is shown
when the bar hits 0%; kill follows once it's certain (shown=True), or
defeated_cancel if YOU DIED came first. Every event carries `game`.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


@dataclass
class Event:
    type: str
    data: dict
    ts: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        return {"type": self.type, "ts": self.ts, **self.data}


Handler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    def __init__(self):
        self._handlers: list[tuple[set[str] | None, Handler]] = []

    def subscribe(self, handler: Handler, types: list[str] | None = None):
        self._handlers.append((set(types) if types else None, handler))

    async def publish(self, event: Event):
        for types, handler in list(self._handlers):
            if types is not None and event.type not in types:
                continue
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # a broken plugin must never stop the counter
                log.exception("event handler %r failed on %s", handler, event.type)


def load_plugins(names: list[str], bus: EventBus, store, config):
    for name in names:
        try:
            module = importlib.import_module(name)
            module.setup(bus=bus, store=store, config=config)
            log.info("loaded plugin %s", name)
        except Exception:
            log.exception("could not load plugin %s", name)


def run_coro_threadsafe(loop: asyncio.AbstractEventLoop, coro):
    return asyncio.run_coroutine_threadsafe(coro, loop)
