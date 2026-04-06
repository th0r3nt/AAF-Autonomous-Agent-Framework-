import socket
import subprocess
from src.cli import ui

REQUIRED_PORTS = {
    5432: "PostgreSQL",
    5672: "RabbitMQ (AMQP)",
}


def is_port_in_use(port: int) -> bool:
    """Проверяет, занят ли порт на localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_port_owned_by_aaf(port: int) -> bool:
    """
    Проверяет, занят ли порт именно контейнерами фреймворка (aaf_postgres / aaf_rabbitmq).
    """
    container_name = "aaf_postgres" if port == 5432 else "aaf_rabbitmq"
    try:
        # Проверяем, крутится ли сейчас наш контейнер
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={container_name}"],
            stdout=subprocess.PIPE,
            text=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def run_all_network_checks():
    """Проверяет порты перед поднятием инфраструктуры."""
    ui.info("Проверка доступности сетевых портов.")

    conflict_found = False

    for port, service_name in REQUIRED_PORTS.items():
        if is_port_in_use(port):
            if is_port_owned_by_aaf(port):
                # Всё ок, это наш старый контейнер, Docker compose его аккуратно перезапустит
                continue

            ui.error(f"Внимание: порт {port} занят чужим процессом. ({service_name})")
            conflict_found = True

    if conflict_found:
        ui.fatal(
            "Найдены сетевые конфликты. Пожалуйста, остановите локальные базы данных,\n"
            "занимающие эти порты, или измените порты в docker-compose.yml."
        )

    ui.success("Сетевые порты свободны.")
