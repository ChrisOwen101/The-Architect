from __future__ import annotations
import asyncio
import logging
import signal
from nio import AsyncClient, AsyncClientConfig, RoomMessageText

from .config import load_config
from .handlers import on_message, set_config
from .matrix_wrapper import MatrixClientWrapper
from .conversation_manager import ConversationManager, set_conversation_manager
from .rate_limiter import RateLimiter, set_rate_limiter

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


async def login_if_needed(client: MatrixClientWrapper, user_id: str, token: str | None):
    """Attach access token to client and ensure user_id is set.

    We rely on a pre-issued access token (no password login here). The nio
    AsyncClient does not populate a user field inside its config object; the
    original code incorrectly tried to read `client.config.user` which does not
    exist leading to AttributeError. We already know the user id from config,
    so we assign it directly. If future logic needs validation we could call
    `await client.whoami()`; for now we skip the additional network round-trip.

    Note: The wrapper forwards attribute access to the underlying client, so
    we can set properties on the wrapper and they'll be set on the wrapped client.
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

    # Initialize conversation manager
    conversation_manager = ConversationManager(
        max_concurrent=cfg.concurrency.max_concurrent_conversations,
        max_per_user=cfg.concurrency.max_conversations_per_user,
        idle_timeout_seconds=cfg.concurrency.conversation_idle_timeout,
        max_duration_seconds=cfg.concurrency.conversation_max_duration
    )
    set_conversation_manager(conversation_manager)
    conversation_manager.start_cleanup_task()
    logger.info("Started conversation manager with cleanup task")

    # Initialize rate limiter
    rate_limiter = RateLimiter(
        rate=cfg.rate_limiting.openai_requests_per_second,
        burst=cfg.rate_limiting.openai_burst_limit
    )
    set_rate_limiter(rate_limiter)
    rate_limiter.start_refill_task()
    logger.info("Started rate limiter with refill task")

    client_cfg = AsyncClientConfig(store_sync_tokens=True)
    base_client = AsyncClient(cfg.homeserver, cfg.user_id,
                              device_id=cfg.device_id, config=client_cfg)

    # Wrap client for thread-safe operations
    client = MatrixClientWrapper(base_client)

    # Register callbacks.
    # nio expects callbacks with the signature (room, event). Our handler also
    # needs the client, so we wrap it in a small adapter that supplies it.
    async def _on_message_wrapper(room, event):  # type: ignore[unused-ignore]
        await on_message(client, room, event)

    # Register callback on base client (nio doesn't use wrapper)
    base_client.add_event_callback(_on_message_wrapper, RoomMessageText)

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

    # Stop background cleanup tasks
    from .user_input_handler import stop_cleanup_task
    stop_cleanup_task()
    logger.info("Stopped user input handler cleanup task")

    conversation_manager.stop_cleanup_task()
    logger.info("Stopped conversation manager cleanup task")

    rate_limiter.stop_refill_task()
    logger.info("Stopped rate limiter refill task")

    # Close OpenAI session
    from .openai_integration import close_openai_session
    await close_openai_session()
    logger.info("Closed OpenAI session")

    await client.close()

if __name__ == "__main__":
    _install_signal_handlers()
    asyncio.run(run())
