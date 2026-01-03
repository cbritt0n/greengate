from __future__ import annotations

import os

from locust import HttpUser, between, task

BASE_URL = os.getenv("GREENGATE_BASE_URL", "http://localhost:8000")
MODEL = os.getenv("GREENGATE_MODEL", "gpt-4o-mini")
PROMPT = os.getenv("GREENGATE_PROMPT", "Share a concise eco tip.")
API_KEY = os.getenv("GREENGATE_API_KEY")


class ChatUser(HttpUser):
    host = BASE_URL
    wait_time = between(1, 3)

    @task
    def send_completion(self):
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a sustainability bot."},
                {"role": "user", "content": PROMPT},
            ],
            "stream": False,
        }
        headers = {}
        if API_KEY:
            headers["Authorization"] = f"Bearer {API_KEY}"

        self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=headers,
            name="chat_completion",
        )

