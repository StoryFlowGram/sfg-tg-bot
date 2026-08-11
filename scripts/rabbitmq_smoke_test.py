import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import aio_pika
from aio_pika import DeliveryMode, Message


async def main() -> None:
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    queue_name = os.getenv("RABBITMQ_SMOKE_TEST_QUEUE", "sfg.word-reminders.smoke-test")
    marker = str(uuid.uuid4())

    payload = {
        "user_id": 1,
        "card_id": 1,
        "word": "smoke",
        "translation": "дим",
        "remind_at": datetime.now(timezone.utc).isoformat(),
        "marker": marker,
    }

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True)

        await channel.default_exchange.publish(
            Message(
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=queue_name,
        )

        message = await queue.get(timeout=10)
        async with message.process():
            received_payload = json.loads(message.body.decode("utf-8"))

        if received_payload.get("marker") != marker:
            raise RuntimeError("Unexpected payload received from RabbitMQ smoke-test queue")

    print(f"RabbitMQ smoke-test passed for queue '{queue_name}'")


if __name__ == "__main__":
    asyncio.run(main())
