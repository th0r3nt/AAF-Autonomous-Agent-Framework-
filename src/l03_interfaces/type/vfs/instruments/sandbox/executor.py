import asyncio
from pathlib import Path

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings

from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.type.vfs.instruments.sandbox.containers import SandboxContainers
from src.l03_interfaces.type.vfs.security.access import VFSAccessController
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class SandboxExecutor(BaseInstrument):
    """
    Инструмент для агента: выполнение Python-скриптов.
    Может работать в двух режимах:
    1. Изолированный (Docker) - по умолчанию.
    2. god_mode - выполнение прямо в ОС сервера (Требует madness_level = 3).
    """

    def __init__(self, client: VFSClient, containers: SandboxContainers):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client
        self.containers = containers

        # Инициализируем контроллер доступа для проверки путей
        project_root = self.client.sandbox_path.parent.parent
        self.access_controller = VFSAccessController(
            sandbox_path=self.client.sandbox_path, project_root=project_root
        )

    async def _run_on_host(self, script_abs_path: Path, timeout: int) -> dict:
        """
        Внутренний метод для выполнения скрипта прямо на ОС сервера (без Docker).
        """
        try:
            # Запускаем отдельный подпроцесс Python
            process = await asyncio.create_subprocess_exec(
                "python",
                str(script_abs_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(script_abs_path.parent),  # Скрипт выполняется в своей родной папке
            )

            try:
                # Ждем выполнения с таймаутом
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                exit_code = process.returncode

                # Декодируем байты в строки
                out_str = stdout.decode("utf-8", errors="replace").strip()
                err_str = stderr.decode("utf-8", errors="replace").strip()

                # Объединяем STDOUT и STDERR
                full_output = out_str
                if err_str:
                    full_output += f"\n[STDERR]:\n{err_str}"

                return {
                    "success": exit_code == 0,
                    "exit_code": exit_code,
                    "output": full_output.strip() or "[Нет вывода в STDOUT/STDERR]",
                }

            except asyncio.TimeoutError:
                # Если скрипт завис (бесконечный цикл, sleep), безжалостно убиваем процесс ОС
                process.kill()
                return {
                    "success": False,
                    "exit_code": "TIMEOUT",
                    "output": f"Скрипт прерван ОС по таймауту ({timeout} сек).",
                }

        except Exception as e:
            return {
                "success": False,
                "exit_code": "CRASH",
                "output": f"Сбой запуска процесса ОС: {e}",
            }

    @skill()
    async def execute_python_script(
        self, filepath: str, timeout: int = 30, run_on_host: bool = False
    ) -> ToolResult:
        """
        Выполняет Python скрипт.

        :param filepath: Путь к скрипту (Относительно sandbox/ или корня проекта в зависимости от прав).
        :param timeout: Максимальное время выполнения в секундах.
        :param run_on_host: Флаг выполнения скрипта на самом сервере, минуя Docker (только God Mode).
        """
        # 1. Запрашиваем безопасный путь у контроллера
        abs_path = self.access_controller.resolve_path(filepath, mode="read")

        if not abs_path:
            return ToolResult.fail(
                msg=f"Ошибка безопасности (Madness Level {settings.system.flags.madness_level}): Доступ к '{filepath}' запрещен.",
                error="Security Error",
            )

        if not abs_path.exists() or not abs_path.is_file():
            return ToolResult.fail(
                msg=f"Ошибка: Файл '{filepath}' не найден или является директорией.",
                error="File Not Found",
            )

        system_logger.info(f"[Executor] Запуск скрипта: {filepath} | Хост-режим: {run_on_host}")

        # 2. Выполнение на ХОСТЕ (God Mode)
        if run_on_host:
            if settings.system.flags.madness_level != 3:
                system_logger.warning(
                    "[Executor] Отклонена попытка выполнения кода на хосте. Требуется God Mode."
                )
                return ToolResult.fail(
                    msg="CRITICAL SECURITY WARNING: Выполнение кода на хосте (run_on_host=True) разрешено только на уровне God Mode (madness_level = 3).",
                    error="Security Restriction",
                )

            result = await self._run_on_host(abs_path, timeout)

        # 3. Выполнение в DOCKER ПЕСОЧНИЦЕ (По умолчанию)
        else:
            if not self.client.is_ready:
                return ToolResult.fail(
                    msg="Ошибка: Docker-демон недоступен. Изолированное выполнение невозможно.",
                    error="Docker Unavailable",
                )

            # Docker жестко пробрасывает только папку sandbox. Он не сможет выполнить скрипт из src/
            if not abs_path.is_relative_to(self.client.sandbox_path):
                return ToolResult.fail(
                    msg="Ошибка: Docker-песочница может запускать только скрипты из папки sandbox/. Для запуска системных скриптов необходимо использовать run_on_host=True.",
                    error="Path Restriction",
                )

            result = await self.containers.run_ephemeral(
                image="python:3.11-alpine", script_abs_path=abs_path, timeout=timeout
            )

        # 4. Обработка вывода
        output = result.get("output", "").strip()

        # Защита контекста LLM: обрезаем слишком длинный вывод
        max_output_length = 30000
        if len(output) > max_output_length:
            output = (
                output[:max_output_length]
                + f"\n\n...[ВЫВОД ОБРЕЗАН: ПРЕВЫШЕН ЛИМИТ В {max_output_length} СИМВОЛОВ]..."
            )

        # 5. Возвращаем результат
        if result.get("success"):
            return ToolResult.ok(
                msg=f"[SUCCESS] Скрипт '{filepath}' успешно выполнен.\n--- ВЫВОД ---\n{output}",
                data=result,
            )
        else:
            exit_code = result.get("exit_code", "Неизвестно")
            return ToolResult.fail(
                msg=f"[ERROR] Ошибка выполнения скрипта '{filepath}' (Код: {exit_code}).\n--- ВЫВОД ---\n{output}",
                error=str(exit_code),
                data=result,
            )
