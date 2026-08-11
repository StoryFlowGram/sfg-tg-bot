import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aio_pika
import aiormq
from aio_pika import DeliveryMode, Message
import httpx
from aiogram import Bot
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ReminderPayload(BaseModel):
    user_id: int
    card_id: int
    word: str
    translation: str
    remind_at: datetime


@dataclass(slots=True)
class NotificationSettings:
    telegram_id: int | None
    notifications_enabled: bool


class ReminderConsumer:
    def __init__(
        self,
        bot: Bot,
        rabbitmq_url: str,
        queue_name: str,
        identity_internal_url: str,
        learning_internal_url: str,
        internal_gateway_token: str,
    ):
        self.bot = bot
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.failed_queue_name = f"{queue_name}.failed"
        self.identity_internal_url = identity_internal_url.rstrip("/")
        self.learning_internal_url = learning_internal_url.rstrip("/")
        self.internal_gateway_token = internal_gateway_token

    async def run_forever(self) -> None:
        while True:
            try:
                await self._consume_once()
            except asyncio.CancelledError:
                raise
            except (
                aiormq.exceptions.AMQPConnectionError,
                aio_pika.exceptions.AMQPConnectionError,
                OSError,
            ) as exc:
                logger.warning(
                    "RabbitMQ unavailable for reminders (%s). Retrying in 5 seconds.",
                    exc,
                )
                await asyncio.sleep(5)
            except Exception:
                logger.exception("Reminder consumer crashed, restarting in 5 seconds")
                await asyncio.sleep(5)

    async def _consume_once(self) -> None:
        connection = await aio_pika.connect_robust(self.rabbitmq_url, fail_fast=False)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)
            await channel.declare_queue(self.failed_queue_name, durable=True)
            queue = await channel.declare_queue(self.queue_name, durable=True)
            logger.info(
                "Connected to RabbitMQ queue '%s' for reminders. Failed queue='%s'",
                self.queue_name,
                self.failed_queue_name,
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    logger.info("Reminder message received from queue '%s'", self.queue_name)
                    try:
                        async with message.process(requeue=False):
                            await self._handle_raw_message(message.body)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "Reminder processing failed. Message moved to queue '%s'",
                            self.failed_queue_name,
                        )
                        await self._publish_failed_message(channel, message.body)

    async def _publish_failed_message(self, channel, body: bytes) -> None:
        try:
            await channel.default_exchange.publish(
                Message(
                    body=body,
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                ),
                routing_key=self.failed_queue_name,
            )
        except Exception:
            logger.exception(
                "Failed to publish broken reminder payload to failed queue '%s'",
                self.failed_queue_name,
            )

    async def _handle_raw_message(self, body: bytes) -> None:
        try:
            payload = ReminderPayload.model_validate_json(body.decode("utf-8"))
        except ValidationError:
            logger.exception("Invalid reminder payload, dropping message")
            return

        logger.info(
            "Reminder payload parsed. user_id=%s card_id=%s remind_at=%s",
            payload.user_id,
            payload.card_id,
            payload.remind_at,
        )

        await self._wait_until_due(payload.remind_at)

        settings = await self._fetch_notification_settings(payload.user_id)
        if settings is None:
            logger.warning("Unable to load notification settings for user %s", payload.user_id)
            return

        if not settings.notifications_enabled:
            logger.info("Notifications disabled for user %s, reminder skipped", payload.user_id)
            return

        if settings.telegram_id is None:
            logger.warning("User %s has no telegram_id; reminder skipped", payload.user_id)
            return

        try:
            due_count = await self._fetch_due_count(payload.user_id)
        except Exception:
            logger.exception("Failed to resolve due count for user %s; fallback to 1", payload.user_id)
            due_count = 1
        if due_count is None:
            logger.warning("Unable to resolve due count for user %s; fallback to 1", payload.user_id)
            due_count = 1
        if due_count <= 0:
            logger.info("User %s has no due cards at reminder time; reminder skipped", payload.user_id)
            return

        logger.info(
            "Sending reminder digest to Telegram. user_id=%s telegram_id=%s due_count=%s",
            payload.user_id,
            settings.telegram_id,
            due_count,
        )
        await self.bot.send_message(
            chat_id=settings.telegram_id,
            text=self._build_message(due_count),
        )
        logger.info(
            "Reminder digest sent successfully. user_id=%s telegram_id=%s due_count=%s",
            payload.user_id,
            settings.telegram_id,
            due_count,
        )

    async def _wait_until_due(self, remind_at: datetime) -> None:
        remind_at_utc = (
            remind_at.astimezone(timezone.utc)
            if remind_at.tzinfo
            else remind_at.replace(tzinfo=timezone.utc)
        )
        delay = (remind_at_utc - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            logger.info("Reminder is scheduled in future, sleeping %.2f seconds", delay)
            await asyncio.sleep(delay)

    async def _fetch_notification_settings(self, user_id: int) -> NotificationSettings | None:
        if not self.internal_gateway_token:
            logger.error("INTERNAL_GATEWAY_TOKEN is empty; cannot resolve notification settings")
            return None

        endpoint = f"{self.identity_internal_url}/users/{user_id}/notification-settings"
        headers = {"X-Gateway-Token": self.internal_gateway_token}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, headers=headers)

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(
                f"Identity internal endpoint returned {response.status_code}: {response.text}"
            )

        data = response.json()
        raw_telegram_id = data.get("telegram_id")
        notifications_enabled = bool(data.get("notifications_enabled", True))

        telegram_id: int | None = None
        if raw_telegram_id is not None:
            try:
                telegram_id = int(raw_telegram_id)
            except (TypeError, ValueError):
                logger.warning("Invalid telegram_id for user %s: %s", user_id, raw_telegram_id)

        return NotificationSettings(
            telegram_id=telegram_id,
            notifications_enabled=notifications_enabled,
        )

    async def _fetch_due_count(self, user_id: int) -> int | None:
        if not self.internal_gateway_token:
            logger.error("INTERNAL_GATEWAY_TOKEN is empty; cannot resolve due count")
            return None

        endpoint = f"{self.learning_internal_url}/due/count"
        headers = {
            "X-Gateway-Token": self.internal_gateway_token,
            "X-User-Id": str(user_id),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, headers=headers)

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(
                f"Learning due-count endpoint returned {response.status_code}: {response.text}"
            )

        data = response.json()
        try:
            return int(data.get("due_count", 0))
        except (TypeError, ValueError):
            logger.warning("Malformed due_count for user %s: %s", user_id, data.get("due_count"))
            return None

    def _build_message(self, due_count: int) -> str:
        noun = self._ukrainian_word_form(due_count)
        return (
            f"У вас {due_count} {noun} на повторення.\n\n"
            "Відкрий StoryFluentGram і пройди повторення."
        )

    def _ukrainian_word_form(self, count: int) -> str:
        abs_count = abs(count)
        last_two = abs_count % 100
        last = abs_count % 10

        if 11 <= last_two <= 14:
            return "слів"
        if last == 1:
            return "слово"
        if 2 <= last <= 4:
            return "слова"
        return "слів"
