from __future__ import annotations

import os

from locust import HttpUser, between, task

BASE_URL = os.getenv("GREENGATE_BASE_URL", "http://localhost:8000")
MODEL = os.getenv("GREENGATE_MODEL", "gpt-4o-mini")
PROMPT = os.getenv("GREENGATE_PROMPT", "Share a concise eco tip.")


class ChatUser(HttpUser):
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
        self.client.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            name="chat_completion",
        )
