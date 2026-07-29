"""
Telegram and Bale expose the same Bot API shape, so one client covers
both — only the base URL and token differ. A future Discord/Slack bot
channel would need its own client, since their APIs differ.
"""
import requests


class BotApiClient:
    def __init__(self, api_base: str, bot_token: str):
        self._api_base = api_base
        self._bot_token = bot_token

    def send_message(self, chat_id: str, text: str) -> None:
        url = f"{self._api_base}/bot{self._bot_token}/sendMessage"
        response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        response.raise_for_status()