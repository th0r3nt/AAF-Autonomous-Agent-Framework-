from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.type.vfs.instruments.sandbox.containers import SandboxContainers
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class SandboxDeployments(BaseInstrument):
    """Управление долгоживущими сервисами и Deployments."""

    def __init__(self, client: 'VFSClient', containers: SandboxContainers):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client
        self.containers = containers

    @skill()
    async def start_service(
        self, name: str, image: str, ports: dict = None, envs: dict = None
    ) -> ToolResult:
        """
        Запускает фоновый долгоживущий сервис в Docker.

        :param name: Уникальное имя сервиса.
        :param image: Docker-образ.
        :param ports: Проброс портов. Словарь {"порт_внутри": "порт_снаружи"}.
        :param envs: Переменные окружения. Словарь {"КЛЮЧ": "ЗНАЧЕНИЕ"}.
        """
        if not self.client.is_ready:
            return ToolResult.fail(msg="Ошибка: Виртуальная файловая система Docker недоступна.")

        # Санитаризация имени (защита от спецсимволов и инъекций)
        clean_name = "".join([c for c in name if c.isalnum() or c in "_-"])
        if not clean_name:
            return ToolResult.fail(
                msg="Ошибка: Имя сервиса должно содержать только буквы, цифры, '_' и '-'."
            )

        # Префикс, чтобы мы всегда могли отличить сервисы агента от системных контейнеров
        full_name = f"aaf_deploy_{clean_name}"

        system_logger.info(f"[Sandbox] Агент запустил сервис: {full_name} ({image})")

        # Вызываем метод из containers.py
        return await self.containers.start_deployment(
            name=full_name, image=image, ports=ports, envs=envs
        )

    @skill()
    async def stop_service(self, name: str) -> ToolResult:
        """
        Останавливает и удаляет работающий сервис.

        :param name: Имя сервиса (которое использовалось при запуске).
        """
        if not self.client.is_ready:
            return ToolResult.fail(msg="Ошибка: Виртуальная файловая система (Docker) недоступна.")

        clean_name = "".join([c for c in name if c.isalnum() or c in "_-"])
        full_name = f"aaf_deploy_{clean_name}"

        system_logger.info(f"[Sandbox] Агент запросил остановку сервиса: {full_name}")

        return await self.containers.stop_deployment(name=full_name)

    @skill()
    async def get_service_logs(self, name: str, tail: int = 50) -> ToolResult:
        """
        Читает последние строки логов работающего сервиса.

        :param name: Имя сервиса.
        :param tail: Количество последних строк.
        """
        if not self.client.is_ready:
            return ToolResult.fail(msg="Ошибка: Docker-демон недоступен.")

        clean_name = "".join([c for c in name if c.isalnum() or c in "_-"])
        full_name = f"aaf_deploy_{clean_name}"

        try:
            # Импортируем docker локально для обработки ошибок
            import docker

            container = self.client.docker_client.containers.get(full_name)

            # Получаем логи
            logs_bytes = container.logs(tail=tail, stdout=True, stderr=True)
            logs_str = logs_bytes.decode("utf-8", errors="replace").strip()

            if not logs_str:
                return ToolResult.ok(msg=f"Логи сервиса '{name}' пусты.", data="")

            return ToolResult.ok(
                msg=f"--- Последние {tail} строк логов сервиса '{name}' ---\n{logs_str}",
                data=logs_str,
            )

        except docker.errors.NotFound:
            return ToolResult.fail(
                msg=f"Ошибка: Сервис '{name}' не запущен или не существует.",
                error="NotFound",
            )

        except Exception as e:
            system_logger.error(f"[Sandbox] Ошибка чтения логов {full_name}: {e}")
            return ToolResult.fail(msg=f"Ошибка чтения логов: {e}", error=str(e))

    @skill()
    async def list_active_services(self) -> ToolResult:
        """
        Возвращает список всех активных фоновых сервисов, запущенных агентом.
        """
        if not self.client.is_ready:
            return ToolResult.fail(msg="Ошибка: Docker-демон недоступен.")

        try:
            # Ищем все контейнеры, чье имя начинается с нашего префикса "aaf_deploy_"
            containers = self.client.docker_client.containers.list(
                all=True, filters={"name": "aaf_deploy_"}
            )

            if not containers:
                return ToolResult.ok(msg="В данный момент нет запущенных сервисов.", data=[])

            result_lines = ["--- Активные сервисы ---"]
            for c in containers:
                # Отрезаем префикс "aaf_deploy_", чтобы агенту было понятнее
                display_name = c.name.replace("aaf_deploy_", "", 1)
                status = c.status.upper()  # RUNNING, EXITED, etc.

                # Достаем проброшенные порты
                ports_info = []
                if c.attrs.get("NetworkSettings", {}).get("Ports"):
                    for int_port, ext_bindings in c.attrs["NetworkSettings"]["Ports"].items():
                        if ext_bindings:
                            for bind in ext_bindings:
                                ports_info.append(f"{bind['HostPort']}->{int_port}")

                ports_str = f" | Порты: {', '.join(ports_info)}" if ports_info else ""

                result_lines.append(
                    f"- Имя: '{display_name}' | Статус: [{status}] | Образ: {c.image.tags[0] if c.image.tags else c.image.id[:10]}{ports_str}"
                )

            return ToolResult.ok(msg="\n".join(result_lines), data=containers)

        except Exception as e:
            system_logger.error(f"[Sandbox] Ошибка листинга сервисов: {e}")
            return ToolResult.fail(msg=f"Ошибка получения списка сервисов: {e}", error=str(e))
