import asyncio
import logging
from contextlib import suppress

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.handlers.start import router_start
from app.middlewares.rate_limit import RateLimitMiddleware
from app.notifications.reminder_consumer import ReminderConsumer
from app.settings.create_bot import (
    bot,
    bot_mode,
    dp,
    drop_pending_updates,
    identity_internal_url,
    internal_gateway_token,
    learning_internal_url,
    messages_per_window,
    rabbitmq_reminder_queue,
    rabbitmq_url,
    start_cooldown_seconds,
    webhook_base_url,
    webhook_host,
    webhook_path,
    webhook_port,
    webhook_secret,
    window_seconds,
)


logger = logging.getLogger(__name__)


def configure_dispatcher() -> None:
    dp.message.middleware(
        RateLimitMiddleware(
            messages_per_window=messages_per_window,
            window_seconds=window_seconds,
            start_cooldown_seconds=start_cooldown_seconds,
        )
    )
    dp.include_router(router_start)


def create_reminder_consumer() -> ReminderConsumer:
    return ReminderConsumer(
        bot=bot,
        rabbitmq_url=rabbitmq_url,
        queue_name=rabbitmq_reminder_queue,
        identity_internal_url=identity_internal_url,
        learning_internal_url=learning_internal_url,
        internal_gateway_token=internal_gateway_token,
    )


async def start_reminder_consumer() -> asyncio.Task:
    reminder_consumer = create_reminder_consumer()
    return asyncio.create_task(reminder_consumer.run_forever())


async def stop_reminder_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def run_polling() -> None:
    reminder_task = await start_reminder_consumer()
    try:
        await bot.delete_webhook(drop_pending_updates=drop_pending_updates)
        await dp.start_polling(bot)
    finally:
        await stop_reminder_task(reminder_task)


def build_webhook_url() -> str:
    if not webhook_base_url:
        raise RuntimeError("WEBHOOK_BASE_URL is required when BOT_MODE=webhook")
    return f"{webhook_base_url.rstrip('/')}{webhook_path}"


def run_webhook() -> None:
    app = web.Application()
    reminder_task: asyncio.Task | None = None

    async def on_startup(_: web.Application) -> None:
        nonlocal reminder_task
        reminder_task = await start_reminder_consumer()
        webhook_url = build_webhook_url()
        await bot.set_webhook(
            url=webhook_url,
            secret_token=webhook_secret or None,
            drop_pending_updates=drop_pending_updates,
        )
        logger.info("Webhook configured. url=%s path=%s", webhook_url, webhook_path)

    async def on_cleanup(_: web.Application) -> None:
        await stop_reminder_task(reminder_task)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret or None,
    ).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    logger.info(
        "Starting webhook server. mode=webhook host=%s port=%s path=%s",
        webhook_host,
        webhook_port,
        webhook_path,
    )
    web.run_app(app, host=webhook_host, port=webhook_port)


def main() -> None:
    configure_dispatcher()
    if bot_mode == "webhook":
        run_webhook()
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
