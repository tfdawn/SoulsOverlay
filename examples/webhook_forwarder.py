"""Example plugin: forward counter events to a chat bot on your VPS.

The counter never opens a port to the internet. Instead this plugin makes an
outbound HTTPS POST for each event, signed with HMAC-SHA256 so the bot can
reject anything that didn't come from you. On the bot side, verify
`X-Signature: sha256=<hex>` over the raw body with the same secret, and use
`X-Timestamp` to drop replays older than a minute.

Enable it in config.toml:

    plugins = ["examples.webhook_forwarder"]

    [plugin_settings.webhook_forwarder]
    url = "https://bot.example.com/souls-overlay"
    secret_env = "SOULSOVERLAY_WEBHOOK_SECRET"   # secret is read from this env var
    events = ["death", "new_pb", "kill", "boss_engaged"]
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time

import aiohttp

log = logging.getLogger(__name__)


def setup(bus, store, config):
    settings = config.plugin_settings.get("webhook_forwarder", {})
    url = settings.get("url")
    secret = os.environ.get(settings.get("secret_env", "SOULSOVERLAY_WEBHOOK_SECRET"), "")
    if not url or not secret:
        log.warning("webhook_forwarder: url or secret missing, not forwarding")
        return
    if not url.startswith("https://"):
        log.warning("webhook_forwarder: refusing non-HTTPS url")
        return
    session: aiohttp.ClientSession | None = None

    async def forward(event):
        nonlocal session
        if session is None:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        body = json.dumps(event.to_json(), separators=(",", ":")).encode()
        ts = str(int(time.time()))
        sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        try:
            async with session.post(url, data=body, headers={
                "Content-Type": "application/json",
                "X-Timestamp": ts,
                "X-Signature": f"sha256={sig}",
            }) as resp:
                if resp.status >= 300:
                    log.warning("webhook_forwarder: %s returned %s", url, resp.status)
        except aiohttp.ClientError as e:
            log.warning("webhook_forwarder: %s", e)

    bus.subscribe(forward, settings.get("events") or None)
