import asyncio
from typing import Optional
import docker
from pathlib import Path
from docker.client import DockerClient
from docker.errors import DockerException

from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Security
from src.l03_interfaces.type.vfs.security.access import VFSAccessController
from src.l03_interfaces.type.vfs.security.backup import ShadowBackupManager

# Инструменты
from src.l03_interfaces.type.vfs.instruments.files.crud import FilesCRUD
from src.l03_interfaces.type.vfs.instruments.files.archive import FilesArchive
from src.l03_interfaces.type.vfs.instruments.files.search import FilesSearch
from src.l03_interfaces.type.vfs.instruments.files.crypto import FilesCrypto
from src.l03_interfaces.type.vfs.instruments.sandbox.containers import SandboxContainers
from src.l03_interfaces.type.vfs.instruments.sandbox.deployments import SandboxDeployments
from src.l03_interfaces.type.vfs.instruments.sandbox.executor import SandboxExecutor


class VFSClient(BaseClient):
    """Низкоуровневый клиент для VFS и Docker."""

    def __init__(self, sandbox_dir: Path):

        self.sandbox_path = sandbox_dir
        self.sandbox_path.mkdir(parents=True, exist_ok=True)

        self.docker_client: Optional[DockerClient] = None
        self.is_ready: bool = False
        self._active_services_cache: list = []

        self._init_docker()

    def register_instruments(self):
        # Вычисляем корень проекта для контроллера доступа
        project_root = self.sandbox_path.parents[1]

        access_controller = VFSAccessController(self.sandbox_path, project_root)
        backup_manager = ShadowBackupManager(project_root)

        FilesCRUD(self, access_controller, backup_manager)
        FilesArchive(self)
        FilesSearch(self)
        FilesCrypto(self)

        containers = SandboxContainers(self)
        SandboxDeployments(self, containers)
        SandboxExecutor(self, containers)

        system_logger.debug("[VFS] Инструменты файловой системы и песочницы зарегистрированы.")

    async def start_background_polling(self) -> None:
        """Фоновый сбор статуса контейнеров, чтобы не блокировать get_passive_context."""
        if not self.is_ready:
            return
            
        async def _docker_poller():
            while True:
                try:
                    # Запускаем синхронный вызов в отдельном потоке, чтобы не блокировать event loop
                    containers = await asyncio.to_thread(
                        self.docker_client.containers.list, filters={"name": "aaf_deploy_"}
                    )
                    self._active_services_cache = [c.name.replace("aaf_deploy_", "") for c in containers]
                except Exception as e:
                    system_logger.debug(f"[VFS Poller] Ошибка обновления кэша контейнеров: {e}")
                
                await asyncio.sleep(30) # Обновляем раз в 30 секунд - этого более чем достаточно

        asyncio.create_task(_docker_poller())

    def get_passive_context(self) -> dict:
        """Мгновенно отдает контекст из ОЗУ."""
        from src.l00_utils.managers.config import settings

        status = "🟢 ONLINE" if self.is_ready else "🔴 OFFLINE"
        madness = settings.interfaces.vfs.madness_level

        return {
            "name": "vfs",
            "status": f"{status} (Madness (file access level): {madness}/3)",
            "active_services": self._active_services_cache, # <--- Берем из кэша
        }

    async def check_connection(self) -> bool:
        if not self.is_ready:
            system_logger.error("[VFS] Docker-клиент не был инициализирован.")
            return False
        is_alive = await asyncio.to_thread(self._sync_check_docker)
        if is_alive:
            system_logger.info(
                f"[VFS] Docker подключен. Sandbox установлен в: {self.sandbox_path}"
            )
            return True
        self.is_ready = False
        return False

    def get_secure_path(self, virtual_path: str) -> Optional[Path]:
        clean_vpath = str(virtual_path).lstrip("/\\")
        target_path = (self.sandbox_path / clean_vpath).resolve()
        if not target_path.is_relative_to(self.sandbox_path):
            system_logger.warning(
                f"[VFS Security] Отклонена попытка выхода из песочницы: {virtual_path}"
            )
            return None
        return target_path

    async def close(self):
        if self.docker_client:
            self.docker_client.close()
            system_logger.info("[VFS] Сессия с Docker закрыта.")

    def _init_docker(self):
        try:
            self.docker_client = docker.from_env()
            self.is_ready = True
        except DockerException as e:
            system_logger.warning(f"[VFS] Ошибка Docker-демона: {e}. Контейнеры недоступны.")
        except Exception as e:
            system_logger.error(f"[VFS] Критический сбой при подключении к Docker: {e}")

    def _sync_check_docker(self) -> bool:
        if not self.docker_client:
            return False
        try:
            self.docker_client.ping()
            return True
        except DockerException:
            return False
