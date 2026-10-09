import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


def send_telegram_message(message: str) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise RuntimeError("Telegram environment variables are missing")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    response = httpx.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
        },
        timeout=20.0,
    )

    response.raise_for_status()