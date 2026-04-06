import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

from src.l00_utils.managers.logger import system_logger


class APIKeyRotator:
    """
    Менеджер ротации API ключей.
    Следит за лимитами (429), отбрасывает уставшие ключи и сбрасывает их раз в сутки.
    """

    def __init__(self, all_keys: List[str]):
        self.all_keys = all_keys

        self.active_keys: List[str] = self.all_keys.copy()
        self.exhausted_keys: List[str] = []

        self.current_index: int = 0
        self.requests_today: int = 0
        self._lock = asyncio.Lock()

        # Файл с состоянием ключей лежит в той же папке, что и этот скрипт
        current_dir = Path(__file__).resolve().parent
        self.state_file = current_dir / "api_keys_state.json"

        if not self.all_keys:
            system_logger.warning(
                "[APIKeyRotator] Внимание: Не найдено ни одного ключа LLM_API_KEY_* в .env."
            )

        msk_tz = timezone(timedelta(hours=3))
        now_msk = datetime.now(msk_tz)

        if now_msk.hour >= 12:
            self.last_reset_date = now_msk.date()
        else:
            self.last_reset_date = now_msk.date() - timedelta(days=1)

        self._sync_load_state()

    def _mask_key(self, key: str) -> str:
        if not key or len(key) <= 10:
            return "[INVALID_KEY]"
        return f"{key[:8]}...[MASKED]"

    def _sync_load_state(self):
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            saved_date_str = state.get("last_reset_date")
            if saved_date_str:
                saved_date = datetime.strptime(saved_date_str, "%Y-%m-%d").date()

                if saved_date == self.last_reset_date:
                    saved_masked_keys = state.get("exhausted_keys", [])
                    self.exhausted_keys = [
                        k for k in self.all_keys if self._mask_key(k) in saved_masked_keys
                    ]
                    self.requests_today = state.get("requests_today", 0)
                    self.active_keys = [
                        k for k in self.all_keys if k not in self.exhausted_keys
                    ]

                    system_logger.info(
                        f"[APIKeyRotator] Состояние восстановлено. Активных ключей: {len(self.active_keys)}"
                    )
        except Exception as e:
            system_logger.error(f"[APIKeyRotator] Ошибка загрузки состояния: {e}")

    def _sync_save_state(self):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "last_reset_date": self.last_reset_date.strftime("%Y-%m-%d"),
                "exhausted_keys": [self._mask_key(k) for k in self.exhausted_keys],
                "requests_today": self.requests_today,
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            system_logger.error(f"[APIKeyRotator] Ошибка сохранения состояния: {e}")

    async def _check_daily_reset(self):
        msk_tz = timezone(timedelta(hours=3))
        now_msk = datetime.now(msk_tz)

        if now_msk.date() > self.last_reset_date and now_msk.hour >= 12:
            if self.exhausted_keys:
                system_logger.info(
                    f"[APIKeyRotator] 12:00 МСК. Сброс квот. Восстановлено ключей: {len(self.exhausted_keys)}"
                )
                self.active_keys.extend(self.exhausted_keys)
                self.exhausted_keys.clear()

            self.requests_today = 0
            self.last_reset_date = now_msk.date()
            await asyncio.to_thread(self._sync_save_state)

    async def get_next_key(self) -> str | None:
        async with self._lock:
            await self._check_daily_reset()

            if not self.active_keys:
                system_logger.critical(
                    "[APIKeyRotator] Все ключи исчерпаны (Rate Limit). Ожидание 12:00 МСК."
                )
                return None

            key = self.active_keys[self.current_index % len(self.active_keys)]
            self.current_index += 1
            self.requests_today += 1

            if self.requests_today % 10 == 0:
                await asyncio.to_thread(self._sync_save_state)

            return key

    async def mark_key_exhausted(self, key: str):
        async with self._lock:
            if key in self.active_keys:
                self.active_keys.remove(key)
                self.exhausted_keys.append(key)

                masked = self._mask_key(key)
                system_logger.warning(
                    f"[APIKeyRotator] Ключ {masked} улетел в лимит (429). Осталось живых: {len(self.active_keys)}"
                )

                if self.active_keys:
                    self.current_index = self.current_index % len(self.active_keys)

                await asyncio.to_thread(self._sync_save_state)

    def get_status(self) -> str:
        return f"Активно: {len(self.active_keys)}/{len(self.all_keys)} | Запросов сегодня: {self.requests_today}"
