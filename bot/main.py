from __future__ import annotations
import asyncio
import logging
import signal
from nio import AsyncClient, AsyncClientConfig, RoomMessageText

from .config import load_config
from .handlers import on_message, set_config

logging.basicConfig(level=logging.INFO,
                    format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("matrix-bot")

STOP = asyncio.Event()


def _install_signal_handlers():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: STOP.set())
        except NotImplementedError:  # Windows
            signal.signal(sig, lambda *_: STOP.set())


async def login_if_needed(client: AsyncClient, user_id: str, token: str | None):
    """Attach access token to client and ensure user_id is set.

    We rely on a pre-issued access token (no password login here). The nio
    AsyncClient does not populate a user field inside its config object; the
    original code incorrectly tried to read `client.config.user` which does not
    exist leading to AttributeError. We already know the user id from config,
    so we assign it directly. If future logic needs validation we could call
    `await client.whoami()`; for now we skip the additional network round-trip.
    """
    if not token:
        raise RuntimeError(
            "Access token must be provided via env var MATRIX_ACCESS_TOKEN")
    client.access_token = token
    # nio sets `client.user_id` when logging in, but since we're injecting an
    # existing token we must set it manually so event handlers can compare.
    client.user_id = user_id  # type: ignore[attr-defined]
    logger.info("Using provided access token for %s", client.user_id)


async def run():
    cfg = load_config()
    set_config(cfg)  # Make config available to handlers
    client_cfg = AsyncClientConfig(store_sync_tokens=True)
    client = AsyncClient(cfg.homeserver, cfg.user_id,
                         device_id=cfg.device_id, config=client_cfg)

    # Register callbacks.
    # nio expects callbacks with the signature (room, event). Our handler also
    # needs the client, so we wrap it in a small adapter that supplies it.
    async def _on_message_wrapper(room, event):  # type: ignore[unused-ignore]
        await on_message(client, room, event)

    client.add_event_callback(_on_message_wrapper, RoomMessageText)

    await login_if_needed(client, cfg.user_id, cfg.access_token)

    # Optionally set display name
    if cfg.display_name:
        try:
            await client.set_displayname(cfg.display_name)
        except Exception:
            logger.warning("Could not set display name", exc_info=True)

    # Start background cleanup task for expired pending questions
    from .user_input_handler import start_cleanup_task
    start_cleanup_task()
    logger.info("Started user input handler cleanup task")

    logger.info("Starting sync loop")

    while not STOP.is_set():
        try:
            resp = await client.sync(timeout=30000)
            if hasattr(resp, 'next_batch'):
                pass
        except Exception:
            logger.exception("Sync failed; retrying in 5s")
            await asyncio.sleep(5)

    logger.info("Shutting down")

    # Stop background cleanup task
    from .user_input_handler import stop_cleanup_task
    stop_cleanup_task()
    logger.info("Stopped user input handler cleanup task")

    await client.close()

if __name__ == "__main__":
    _install_signal_handlers()
    asyncio.run(run())
