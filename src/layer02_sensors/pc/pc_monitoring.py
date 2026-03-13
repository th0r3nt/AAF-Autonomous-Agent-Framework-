import asyncio
from src.layer00_utils.logger import system_logger
from src.layer02_sensors.pc.voice.stt import stt_loop

class PCMonitoring:
    def __init__(self):
        self.tasks = []

    async def run_loop(self):
        """Запуск потоков мониторинга ПК"""
        try:
            self.tasks.append(asyncio.create_task(stt_loop())) # Работает постоянно для мониторинга голосовых команд

            await asyncio.gather(*self.tasks)

        except Exception as e:
            system_logger.error(f"Ошибка при мониторинге ПК: {e}")

pc_monitoring = PCMonitoring()
