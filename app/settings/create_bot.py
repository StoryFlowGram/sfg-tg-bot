import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

load_dotenv()


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name, str(default)).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _get_str_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_required_str_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


bot = Bot(token=_get_required_str_env("BOT_TOKEN"))
dp = Dispatcher()

messages_per_window = _get_int_env("BOT_MESSAGES_PER_MINUTE", 20)
window_seconds = _get_int_env("BOT_RATE_LIMIT_WINDOW_SECONDS", 60)
start_cooldown_seconds = _get_int_env("BOT_START_COOLDOWN_SECONDS", 10)

rabbitmq_url = _get_required_str_env("RABBITMQ_URL")
rabbitmq_reminder_queue = _get_str_env("RABBITMQ_REMINDER_QUEUE", "sfg.word-reminders")
identity_internal_url = _get_required_str_env("IDENTITY_INTERNAL_URL")
learning_internal_url = _get_required_str_env("LEARNING_INTERNAL_URL")
internal_gateway_token = _get_required_str_env("INTERNAL_GATEWAY_TOKEN")

bot_mode = _get_str_env("BOT_MODE", "polling").lower()
webhook_base_url = _get_str_env("WEBHOOK_BASE_URL")
webhook_path = _get_str_env("WEBHOOK_PATH", "/telegram/webhook")
if not webhook_path.startswith("/"):
    webhook_path = f"/{webhook_path}"
webhook_secret = _get_str_env("WEBHOOK_SECRET")
webhook_host = _get_str_env("WEBHOOK_HOST", "0.0.0.0")
webhook_port = _get_int_env("WEBHOOK_PORT", 8080)
drop_pending_updates = _get_bool_env("DROP_PENDING_UPDATES", True)
