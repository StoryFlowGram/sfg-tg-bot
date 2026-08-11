# Telegram Bot Service

> Telegram interface microservice for StoryFluentGram. Handles Telegram WebApp launches, user interaction, and automated spaced-repetition word reminders via RabbitMQ.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Running the Service](#running-the-service)
- [Environment Variables](#environment-variables)
- [API & Handlers](#api--handlers)
- [Project Structure](#project-structure)

---

## Overview

Bot Service provides the Telegram gateway for users:

- **Telegram WebApp entrypoint**: Serves `/start` command with inline buttons launching the WebApp interface
- **Word Repetition Reminders**: Consumes `sfg.word-reminders` messages from RabbitMQ published by `learning-service` and sends push notifications to Telegram users
- **Internal Integration**: Fetches user identity and due cards via internal HTTP APIs (`identity-service` and `learning-service`)
- **Dual Mode**: Supports both `polling` and `webhook` operation modes

---

## Architecture

```
Telegram User ──▶ Telegram API ──▶ Bot Service (polling / webhook)
                                        │
                                        ├──▶ RabbitMQ (sfg.word-reminders consumer)
                                        ├──▶ Identity Service (internal HTTP)
                                        └──▶ Learning Service (internal HTTP)
```

---

## Technology Stack

| Package | Version | Role |
|--------|---------|------|
| `aiogram` | 3.13.1 | Asynchronous Telegram Bot framework |
| `aio-pika` | ^9.5.7 | RabbitMQ async consumer |
| `httpx` | ^0.28.1 | Async HTTP client for internal services |
| `python-dotenv` | ^1.2.1 | Environment management |
| `loguru` | ^0.7.3 | Structured logging |
| Python | ≥ 3.12 | Runtime |

---

## Running the Service

### Locally (Poetry)

```bash
cd bot-service
cp .env.example .env
poetry install
python main.py
```

### Docker

```bash
docker build -t sfg-bot-service .
docker run --env-file .env sfg-bot-service
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram Bot API token from @BotFather | `1234567890:ABC...` |
| `BOT_MODE` | Operation mode (`polling` or `webhook`) | `polling` |
| `WEB_APP_URL` | URL of the deployed Frontend WebApp | `https://example.com` |
| `RABBITMQ_URL` | AMQP connection string | `amqp://guest:guest@rabbitmq:5672/` |
| `RABBITMQ_REMINDER_QUEUE` | Queue name for reminders | `sfg.word-reminders` |
| `IDENTITY_INTERNAL_URL` | Internal URL for identity service | `http://identity-service:8000/internal` |
| `LEARNING_INTERNAL_URL` | Internal URL for learning service | `http://learning-service:8000` |
| `INTERNAL_GATEWAY_TOKEN` | Shared secret token for inter-service calls | `replace_me` |

---

## API & Handlers

### Bot Commands

- `/start` — Welcomes the user and presents a button to launch the WebApp.

### Background Workers

- **Reminder Consumer**: Listens on `sfg.word-reminders` queue, looks up user Telegram chat IDs, formats due word cards, and dispatches Telegram notification messages.

---

## Project Structure

```
bot-service/
├── main.py                   # Bot entrypoint (polling & webhook servers)
├── app/
│   ├── handlers/             # Bot command handlers (/start)
│   ├── middlewares/          # Rate limiting middleware
│   ├── notifications/        # RabbitMQ reminder consumer
│   └── settings/             # Environment configuration & bot initialization
├── Dockerfile
└── pyproject.toml
```
