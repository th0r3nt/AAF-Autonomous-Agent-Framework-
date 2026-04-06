import os
import asyncio
from pathlib import Path
from docker.errors import ImageNotFound, APIError, NotFound

from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class SandboxContainers(BaseInstrument):
    """
    CRUD-движок для безопасного управления Docker контейнерами.
    Изолирует выполнение скриптов агента и управляет его долгоживущими сервисами.
    """

    def __init__(self, client: 'VFSClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.client = client
        self.sandbox_path = self.client.sandbox_path

        # Имя долгоживущего контейнера-исполнителя
        self.REPL_CONTAINER_NAME = "aaf_python_repl"

    # ==========================================
    # FAST REPL EXECUTOR (Вместо Ephemeral)
    # ==========================================

    def _ensure_repl_container(self, image: str = "python:3.11-alpine"):
        """
        Проверяет, жив ли REPL-контейнер. Если нет - поднимает его.
        Он будет просто спать (tail -f /dev/null), ожидая команд от агента.
        """
        if not self.client.docker_client:
            raise RuntimeError("Docker-демон не подключен.")

        try:
            # Пытаемся найти существующий контейнер
            container = self.client.docker_client.containers.get(self.REPL_CONTAINER_NAME)
            if container.status != "running":
                container.start()
            return container

        except NotFound:
            system_logger.info(f"[Sandbox] Инициализация быстрого REPL-контейнера ({image}).")

            # УМНЫЙ МАППИНГ ПУТЕЙ (DooD Fix)
            # Если мы работаем в Docker (agent_core), нам нужен путь с хоста (ПК пользователя)
            host_workspace = os.getenv("HOST_WORKSPACE_PATH")
            
            if host_workspace:
                # Docker Desktop на Windows отлично понимает пути вида C:\...
                host_sandbox = Path(host_workspace) / "agent" / "sandbox"
                mount_source = str(host_sandbox)
                system_logger.debug(f"[Sandbox] DooD режим активен. Монтируем с хоста: {mount_source}")
            else:
                # Если запускаем скрипт локально из IDE (без Docker для agent_core)
                mount_source = str(self.sandbox_path.resolve())
                system_logger.debug(f"[Sandbox] Локальный режим активен. Монтируем: {mount_source}")

            # Монтируем песочницу хоста в /sandbox контейнера-исполнителя
            volumes = {mount_source: {"bind": "/sandbox", "mode": "rw"}}

            try:
                container = self.client.docker_client.containers.run(
                    image=image,
                    name=self.REPL_CONTAINER_NAME,
                    command=[
                        "tail",
                        "-f",
                        "/dev/null",
                    ],  # Бесконечный сон, не потребляющий CPU
                    volumes=volumes,
                    working_dir="/sandbox",
                    detach=True,
                    network_mode="bridge",
                    mem_limit="512m",
                    cpu_quota=50000,
                    restart_policy={"Name": "always"},
                )
                return container
            except ImageNotFound:
                raise RuntimeError(
                    f"Образ '{image}' не найден. Необходимо сделать 'docker pull {image}'."
                )

    def _sync_run_ephemeral(self, image: str, script_abs_path: Path, timeout: int) -> ToolResult:
        """
        Синхронная логика мгновенного запуска скрипта через exec_run.
        """
        try:
            container = self._ensure_repl_container(image)
        except RuntimeError as e:
            return ToolResult.fail(msg=str(e), error="Docker connection error")

        # Вычисляем относительный путь скрипта внутри песочницы
        try:
            rel_path = script_abs_path.relative_to(self.sandbox_path)
            # Внутри REPL-контейнера папка всегда называется /sandbox
            internal_path = f"/sandbox/{rel_path.as_posix()}"
        except ValueError:
            return ToolResult.fail(
                msg="Ошибка безопасности: Скрипт находится вне песочницы.",
                error="PathError",
            )

        try:
            system_logger.debug(f"[Sandbox] Мгновенное выполнение {script_abs_path.name} в REPL...")

            # Используем встроенную в Alpine утилиту 'timeout', чтобы убить процесс, если агент написал бесконечный цикл (while True)
            cmd = ["timeout", str(timeout), "python", internal_path]

            # Впрыскиваем процесс в уже работающий контейнер (Это занимает миллисекунды)
            exit_code, output = container.exec_run(cmd=cmd, workdir="/sandbox")

            # Декодируем вывод
            out_str = output.decode("utf-8", errors="replace").strip()

            # Коды 143 (SIGTERM) или 124 (Timeout) возвращаются линуксовой утилитой timeout
            if exit_code in [143, 124]:
                return ToolResult.fail(
                    msg=f"Скрипт прерван по таймауту ({timeout} сек).\nПоследние логи:\n{out_str}",
                    error="Timeout",
                )

            output_msg = out_str or "[Нет вывода в STDOUT/STDERR]"

            return (
                ToolResult.ok(msg=output_msg, data={"exit_code": exit_code})
                if exit_code == 0
                else ToolResult.fail(msg=output_msg, error=f"Exit code {exit_code}")
            )

        except APIError as e:
            return ToolResult.fail(msg=f"Docker API Ошибка: {e}", error=str(e))

    # ==========================================
    # LONG-RUNNING DEPLOYMENTS
    # ==========================================

    def _sync_start_deployment(
        self, name: str, image: str, ports: dict = None, envs: dict = None
    ) -> ToolResult:
        """
        Запускает долгоживущий сервис агента.
        """
        if not self.client.docker_client:
            return ToolResult.fail(
                msg="Ошибка: Docker-демон не подключен.",
                error="Docker connection error",
            )

        try:
            existing = self.client.docker_client.containers.get(name)
            return ToolResult.fail(
                msg=f"Ошибка: Сервис с именем '{name}' уже запущен (Статус: {existing.status}).",
                error="Conflict",
            )
        except NotFound:
            pass

        try:
            container = self.client.docker_client.containers.run(
                image=image,
                name=name,
                ports=ports or {},
                environment=envs or {},
                detach=True,
                restart_policy={"Name": "always"},
            )
            system_logger.info(f"[Sandbox] Поднят сервис '{name}' (ID: {container.short_id})")
            return ToolResult.ok(
                msg=f"Сервис '{name}' успешно запущен на базе образа '{image}'.",
                data={"container_id": container.id},
            )

        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка запуска сервиса: {e}", error=str(e))

    def _sync_stop_deployment(self, name: str) -> ToolResult:
        """
        Останавливает и удаляет сервис.
        """
        if not self.client.docker_client:
            return ToolResult.fail(
                msg="Ошибка: Docker-демон не подключен.",
                error="Docker connection error",
            )

        try:
            container = self.client.docker_client.containers.get(name)
            container.stop(timeout=5)
            container.remove(force=True)
            system_logger.info(f"[Sandbox] Сервис '{name}' остановлен и удален.")
            return ToolResult.ok(msg=f"Сервис '{name}' успешно остановлен и удален.")

        except NotFound:
            return ToolResult.fail(msg=f"Ошибка: Сервис '{name}' не найден.", error="NotFound")

        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка при остановке сервиса: {e}", error=str(e))

    # ==========================================
    # АСИНХРОННЫЕ ФАСАДЫ
    # ==========================================

    @skill()
    async def run_ephemeral(
        self, image: str, script_abs_path: Path, timeout: int = 30
    ) -> ToolResult:
        """Запускает скрипт мгновенно через REPL-контейнер."""
        return await asyncio.to_thread(self._sync_run_ephemeral, image, script_abs_path, timeout)

    @skill()
    async def start_deployment(
        self, name: str, image: str, ports: dict = None, envs: dict = None
    ) -> ToolResult:
        """Запускает долгоживущий сервис."""
        return await asyncio.to_thread(self._sync_start_deployment, name, image, ports, envs)

    @skill()
    async def stop_deployment(self, name: str) -> ToolResult:
        """Останавливает долгоживущий сервис."""
        return await asyncio.to_thread(self._sync_stop_deployment, name)