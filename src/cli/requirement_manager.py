import sys
import subprocess
import importlib
import importlib.metadata

# Теперь мы ищем именно имена пакетов (как они записаны в pip), а не имена модулей
CLI_DEPENDENCIES = ["typer", "rich", "python-dotenv", "pyyaml", "docker", "questionary"]


def check_and_install_dependencies():
    """
    Проверяет наличие базовых библиотек для работы CLI лаунчера.
    Использует проверку метаданных пакетов, что на 100% надежно.
    """
    missing_packages = []

    for pip_name in CLI_DEPENDENCIES:
        try:
            # Ищем пакет в реестре установленных библиотек (аналог pip show)
            importlib.metadata.version(pip_name)
        except importlib.metadata.PackageNotFoundError:
            missing_packages.append(pip_name)

    if missing_packages:
        print(f"\n[AAF Bootstrapper] Отсутствуют пакеты: {', '.join(missing_packages)}")
        print("[AAF Bootstrapper] Запуск установки.\n")

        try:
            # Запускаем pip install через текущий интерпретатор
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    *missing_packages,
                    "--disable-pip-version-check",
                ],
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            print("\n[AAF Bootstrapper] ✔ Библиотеки успешно установлены.\n")

            # Сбрасываем кэш импортов, чтобы интерпретатор увидел новые библиотеки
            importlib.invalidate_caches()

        except subprocess.CalledProcessError as e:
            print(
                f"\n[AAF Bootstrapper] ✖ Ошибка автоматической установки (Код: {e.returncode})."
            )
            print("Пожалуйста, установите их вручную командой:\n")
            print(f"{sys.executable} -m pip install {' '.join(missing_packages)}\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n[AAF Bootstrapper] ✖ Непредвиденная ошибка: {e}")
            sys.exit(1)
