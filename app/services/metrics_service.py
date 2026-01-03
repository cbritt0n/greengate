from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from app.core.config import settings


class EnergyLedger:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS energy_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        spent REAL NOT NULL,
                        saved REAL NOT NULL,
                        prompt_tokens INTEGER NOT NULL,
                        completion_tokens INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                await db.commit()
            self._initialized = True

    async def record(
        self,
        *,
        spent: float,
        saved: float,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                (
                    "INSERT INTO energy_metrics (spent, saved, prompt_tokens, completion_tokens) "
                    "VALUES (?, ?, ?, ?)"
                ),
                (max(spent, 0.0), max(saved, 0.0), prompt_tokens, completion_tokens),
            )
            await db.commit()

    async def snapshot(self) -> dict[str, float]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*), SUM(spent), SUM(saved) FROM energy_metrics"
            ) as cursor:
                row = await cursor.fetchone()
        requests = row[0] or 0
        spent = row[1] or 0.0
        saved = row[2] or 0.0
        return {"requests": float(requests), "energy_spent": spent, "energy_saved": saved}

    async def average_per_request(self) -> dict[str, float]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT AVG(spent), AVG(saved) FROM energy_metrics"
            ) as cursor:
                row = await cursor.fetchone()
        avg_spent = row[0] or 0.0
        avg_saved = row[1] or 0.0
        return {"spent": avg_spent, "saved": avg_saved}


energy_ledger = EnergyLedger(settings.ledger_path())
