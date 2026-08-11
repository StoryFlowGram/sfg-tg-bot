import asyncio
import math
import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import Message


class RateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        messages_per_window: int = 20,
        window_seconds: int = 60,
        start_cooldown_seconds: int = 10,
    ):
        self.messages_per_window = max(1, messages_per_window)
        self.window_seconds = max(1, window_seconds)
        self.start_cooldown_seconds = max(1, start_cooldown_seconds)

        self._message_timestamps: dict[int, deque[float]] = defaultdict(deque)
        self._last_start_at: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def __call__(self, handler, event, data):
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        text = (event.text or "").strip().lower()
        is_start_command = text.startswith("/start")
        now = time.monotonic()

        async with self._lock:
            queue = self._message_timestamps[user_id]
            while queue and now - queue[0] > self.window_seconds:
                queue.popleft()

            if len(queue) >= self.messages_per_window:
                await event.answer("Ви надсилаєте запити занадто часто. Спробуйте трохи пізніше.")
                return

            queue.append(now)

            if is_start_command:
                last_start = self._last_start_at.get(user_id)
                if last_start is not None and now - last_start < self.start_cooldown_seconds:
                    wait_seconds = math.ceil(self.start_cooldown_seconds - (now - last_start))
                    await event.answer(
                        f"Команду /start можна повторити через {wait_seconds} с."
                    )
                    return
                self._last_start_at[user_id] = now

        return await handler(event, data)
